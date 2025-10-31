from __future__ import annotations

from typing import Any, Dict, List, Optional

from bson import ObjectId
from flask import Blueprint, current_app, jsonify, request

from .db import get_collection
from .voyage import get_client

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


def build_filter_clause(
    available: Optional[bool], max_price: Optional[float], restaurant: Optional[str]
) -> Dict[str, Any]:
    conditions: List[Dict[str, Any]] = []

    if available is not None:
        conditions.append({"product.available": available})

    if max_price is not None:
        conditions.append({"product.price.amount": {"$lt": max_price}})

    if restaurant:
        conditions.append({"restaurantName": restaurant})

    if not conditions:
        return {}

    if len(conditions) == 1:
        return {"filter": conditions[0]}

    return {"filter": {"$and": conditions}}


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

    return result


@api_bp.route("/restaurants", methods=["GET"])
def list_restaurants():
    collection = get_collection()
    pipeline = [
        {"$group": {"_id": "$restaurantName"}},
        {"$match": {"_id": {"$ne": None}}},
        {"$sort": {"_id": 1}},
    ]
    restaurants = [doc["_id"] for doc in collection.aggregate(pipeline)]
    return jsonify(restaurants)


@api_bp.route("/search", methods=["POST"])
def search_products():
    payload = request.get_json(silent=True) or {}
    query = (payload.get("query") or "").strip()

    if not query:
        return jsonify({"message": "La descripción es obligatoria."}), 400

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

    voyage_client = get_client()
    text_model = current_app.config.get("VOYAGE_TEXT_MODEL", "voyage-3.5")

    try:
        embedding_response = voyage_client.embed(texts=[query], model=text_model)
        vectors = extract_embeddings(embedding_response)
        query_vector = vectors[0]
    except Exception as exc:  # pylint: disable=broad-except
        return jsonify({"message": f"No fue posible generar el embedding: {exc}"}), 500

    index_name = current_app.config.get("VECTOR_INDEX_NAME") or current_app.config.get("ATLAS_SEARCH_INDEX")
    if not index_name:
        return jsonify({"message": "No hay un índice de vector search configurado."}), 500

    vector_stage: Dict[str, Any] = {
        "$vectorSearch": {
            "index": index_name,
            "path": "emb_description",
            "queryVector": query_vector,
            "limit": limit,
            "numCandidates": num_candidates,
        }
    }

    filter_clause = build_filter_clause(available, max_price, restaurant)
    if filter_clause:
        vector_stage["$vectorSearch"].update(filter_clause)

    pipeline = [
        vector_stage,
        {
            "$project": {
                "_id": 1,
                "restaurantName": 1,
                "product": 1,
                "score": {"$meta": "vectorSearchScore"},
            }
        },
    ]

    collection = get_collection()
    try:
        cursor = collection.aggregate(pipeline)
        results = [sanitize_result(doc) for doc in cursor]
    except Exception as exc:  # pylint: disable=broad-except
        return jsonify({"message": f"No fue posible ejecutar la búsqueda: {exc}"}), 500

    return jsonify({"results": results})
