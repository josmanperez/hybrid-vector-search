from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

from bson import ObjectId, json_util
from flask import Blueprint, current_app, jsonify, request

from .db import get_collection
from .voyage import get_client
from utils.logger import get_logger

api_bp = Blueprint("api", __name__, url_prefix="/api")


def extract_embeddings(response) -> List[List[float]]:
    embeddings = getattr(response, "embeddings", None)
    if embeddings is None:
        raise ValueError("Voyage response did not contain embeddings.")
    vectors: List[List[float]] = []
    for item in embeddings:
        if hasattr(item, "embedding"):
            vectors.append(item.embedding)  # type: ignore[attr-defined]
        else:
            vectors.append(item)
    return vectors


def build_filter_components(
    available: Optional[bool], max_price: Optional[float], restaurant: Optional[str]
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    conditions: List[Dict[str, Any]] = []

    if available is not None:
        conditions.append({"product.available": available})

    if max_price is not None:
        conditions.append({"product.price.amount": {"$lt": max_price}})

    if restaurant:
        conditions.append({"restaurantName": restaurant})

    if not conditions:
        return None, None

    if len(conditions) == 1:
        return conditions[0], conditions[0]

    combined = {"$and": conditions}
    return combined, combined


def sanitize_result(document: Dict[str, Any]) -> Dict[str, Any]:
    result = dict(document)

    if isinstance(result.get("_id"), ObjectId):
        result["_id"] = str(result["_id"])

    if "score" in result:
        try:
            result["score"] = float(result["score"])
        except (TypeError, ValueError):
            pass

    product = result.get("product")
    if isinstance(product, dict):
        product_copy = dict(product)
        if isinstance(product_copy.get("_id"), ObjectId):
            product_copy["_id"] = str(product_copy["_id"])
        price = product_copy.get("price")
        if isinstance(price, dict) and "amount" in price:
            try:
                price["amount"] = float(price["amount"])
            except (TypeError, ValueError):
                pass
        result["product"] = product_copy

    if "scoreDetails" in result:
        result["scoreDetails"] = json.loads(json_util.dumps(result["scoreDetails"]))

    return result


@api_bp.route("/restaurants", methods=["GET"])
def list_restaurants():
    collection = get_collection()
    pipeline = [
        {"$group": {"_id": "$restaurantName"}},
        {"$match": {"_id": {"$ne": None}}},
        {"$sort": {"_id": 1}},
    ]
    logger = get_logger("api")
    logger.info("Executing restaurants aggregation: %s", pipeline)
    restaurants = [doc["_id"] for doc in collection.aggregate(pipeline)]
    return jsonify(restaurants)


@api_bp.route("/search", methods=["POST"])
def search_products():
    payload = request.get_json(silent=True) or {}
    logger = get_logger("api")
    mode = (payload.get("mode") or "vector").lower()
    if mode not in {"vector", "hybrid", "fulltext"}:
        return jsonify({"message": "Modo de búsqueda no válido."}), 400

    description = (payload.get("description") or "").strip()
    title_value = (payload.get("title") or "").strip()

    if mode in {"vector", "hybrid"} and not description:
        return jsonify({"message": "La descripción es obligatoria para la búsqueda seleccionada."}), 400

    if mode in {"hybrid", "fulltext"} and not title_value:
        return jsonify({"message": "El título es obligatorio para la búsqueda seleccionada."}), 400

    try:
        limit = int(payload.get("limit", 5))
    except (TypeError, ValueError):
        limit = 5
    limit = max(1, min(limit, 25))
    num_candidates = limit * 20

    available = payload.get("available")
    if available is not None:
        available = bool(available)

    max_price = payload.get("maxPrice")
    if max_price is not None:
        try:
            max_price = float(max_price)
        except (TypeError, ValueError):
            return jsonify({"message": "El formato del precio máximo no es válido."}), 400

    restaurant = payload.get("restaurant")
    if restaurant is not None:
        restaurant = restaurant.strip()
        if not restaurant:
            restaurant = None

    logger.info(
        "Search request mode=%s description_length=%d title_length=%d limit=%d filters=%s",
        mode,
        len(description),
        len(title_value),
        limit,
        {"available": available, "max_price": max_price, "restaurant": restaurant},
    )

    query_vector: Optional[List[float]] = None
    vector_stage: Optional[Dict[str, Any]] = None
    filter_doc: Optional[Dict[str, Any]] = None
    match_clause: Optional[Dict[str, Any]] = None

    if mode in {"vector", "hybrid"}:
        voyage_client = get_client()
        text_model = current_app.config.get("VOYAGE_TEXT_MODEL", "voyage-3.5")

        try:
            embedding_response = voyage_client.embed(texts=[description], model=text_model)
            vectors = extract_embeddings(embedding_response)
            query_vector = vectors[0]
        except Exception as exc:  # pylint: disable=broad-except
            return jsonify({"message": f"No fue posible generar el embedding: {exc}"}), 500

        vector_index = current_app.config.get("VECTOR_INDEX_NAME") or current_app.config.get("ATLAS_SEARCH_INDEX")
        if not vector_index:
            return jsonify({"message": "No hay un índice vectorial configurado."}), 500

        vector_stage = {
            "$vectorSearch": {
                "index": vector_index,
                "path": "emb_description",
                "queryVector": query_vector,
                "limit": limit,
                "numCandidates": num_candidates,
            }
        }

        filter_doc, match_clause = build_filter_components(available, max_price, restaurant)
        if filter_doc:
            vector_stage["$vectorSearch"]["filter"] = filter_doc
    else:
        _, match_clause = build_filter_components(available, max_price, restaurant)

    collection = get_collection()

    if mode == "vector":
        if vector_stage is None:
            return jsonify({"message": "No se pudo preparar la búsqueda vectorial."}), 500
        pipeline = [
            vector_stage,
            {
                "$project": {
                    "_id": 1,
                    "restaurantName": 1,
                    "product": 1,
                    "title": 1,
                    "score": {"$meta": "vectorSearchScore"},
                }
            },
            {"$limit": limit},
        ]
        logger.info("Executing vector pipeline: %s", pipeline)
    elif mode == "hybrid":
        if vector_stage is None:
            return jsonify({"message": "No se pudo preparar la búsqueda híbrida."}), 500

        text_index = current_app.config.get("FULL_TEXT_INDEX_NAME", "full-text-search")
        score_fusion_stage: Dict[str, Any] = {
            "$scoreFusion": {
                "input": {
                    "pipelines": {
                        "searchOne": [vector_stage],
                        "searchTwo": [
                            {
                                "$search": {
                                    "index": text_index,
                                    "text": {"query": title_value, "path": "title"},
                                }
                            }
                        ],
                    },
                    "normalization": "sigmoid",
                },
                "combination": {
                    "method": "expression",
                    "expression": {
                        "$sum": [
                            {"$multiply": ["$$searchOne", 10]},
                            "$$searchTwo",
                        ]
                    },
                },
                "scoreDetails": True,
            }
        }

        pipeline = [score_fusion_stage]
        if match_clause:
            pipeline.append({"$match": match_clause})
        pipeline.extend(
            [
                {
                    "$project": {
                        "_id": 1,
                        "restaurantName": 1,
                        "product": 1,
                        "title": 1,
                        "scoreDetails": {"$meta": "scoreDetails"},
                    }
                },
                {"$limit": limit},
            ]
        )
        logger.info("Executing score fusion pipeline: %s", pipeline)
    else:  # fulltext simple
        text_index = current_app.config.get("FULL_TEXT_INDEX_NAME", "full-text-search")
        pipeline = [
            {
                "$search": {
                    "index": text_index,
                    "text": {"query": title_value, "path": "title"},
                }
            }
        ]
        if match_clause:
            pipeline.append({"$match": match_clause})
        pipeline.extend(
            [
                {
                    "$project": {
                        "_id": 1,
                        "restaurantName": 1,
                        "product": 1,
                        "title": 1,
                        "score": {"$meta": "searchScore"},
                    }
                },
                {"$limit": limit},
            ]
        )
        logger.info("Executing full-text pipeline: %s", pipeline)

    try:
        print(pipeline)
        cursor = collection.aggregate(pipeline)
        results = [sanitize_result(doc) for doc in cursor]
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("Aggregation failed: %s", exc)
        return jsonify({"message": f"No fue posible ejecutar la búsqueda: {exc}"}), 500

    return jsonify({"mode": mode, "results": results})
