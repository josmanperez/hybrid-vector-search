import argparse
import json
import os
from typing import Any, Dict, List

from dotenv import load_dotenv
from pymongo import MongoClient
from voyageai import Client


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Execute a local vector search against the products collection.")
    parser.add_argument("query", help="Query string to embed and search for (wrap in quotes when calling from the terminal).")
    parser.add_argument("--k", type=int, default=5, help="Number of results to return from the vector search.")
    parser.add_argument(
        "--similarity",
        default=os.getenv("VECTOR_INDEX_SIMILARITY", "cosine"),
        choices=["cosine", "dotProduct", "euclidean"],
        help="Similarity metric to use in the search (must match the index configuration).",
    )
    parser.add_argument(
        "--filter-available",
        type=str,
        choices=["true", "false"],
        help="Optional availability filter. Pass 'true' or 'false'.",
    )
    parser.add_argument(
        "--min-price",
        type=float,
        help="Optional minimum price filter using products.price.amount.",
    )
    parser.add_argument(
        "--max-price",
        type=float,
        help="Optional maximum price filter using products.price.amount.",
    )
    return parser.parse_args()


def load_settings() -> Dict[str, str]:
    load_dotenv()
    mongo_uri = os.getenv("MONGODB_URI")
    db_name = os.getenv("DB_NAME")
    collection_name = os.getenv("PRODUCT_DETAIL_COLLECTION")
    api_key = os.getenv("VOYAGE_API_KEY")
    text_model = os.getenv("VOYAGE_TEXT_MODEL", "voyage-3.5")
    index_name = os.getenv("VECTOR_INDEX_NAME") or os.getenv("ATLAS_SEARCH_INDEX") or "products_vector_index"

    missing = [
        name
        for name, value in [
            ("MONGODB_URI", mongo_uri),
            ("DB_NAME", db_name),
            ("COLLECTION_NAME", collection_name),
            ("VOYAGE_API_KEY", api_key),
        ]
        if not value
    ]
    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")

    return {
        "mongo_uri": mongo_uri,
        "db_name": db_name,
        "collection_name": collection_name,
        "api_key": api_key,
        "text_model": text_model,
        "index_name": index_name,
    }


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


def build_filter_clause(args: argparse.Namespace) -> Dict[str, Any]:
    clauses: List[Dict[str, Any]] = []

    if args.filter_available is not None:
        clauses.append(
            {
                "equals": {
                    "path": "product.available",
                    "value": args.filter_available.lower() == "true",
                }
            }
        )

    price_clause: Dict[str, Any] = {}
    if args.min_price is not None:
        price_clause.setdefault("gte", args.min_price)
    if args.max_price is not None:
        price_clause.setdefault("lte", args.max_price)
    if price_clause:
        clauses.append(
            {
                "range": {
                    "path": "product.price.amount",
                    **price_clause,
                }
            }
        )

    if not clauses:
        return {}

    if len(clauses) == 1:
        return {"filter": clauses[0]}

    return {
        "filters": [
            {
                "must": clauses,
            }
        ]
    }


def main() -> None:
    args = parse_args()
    settings = load_settings()

    client = Client(api_key=settings["api_key"])
    mongo_client = MongoClient(settings["mongo_uri"])

    try:
        # Generate embedding for the incoming query.
        embedding_response = client.embed(texts=[args.query], model=settings["text_model"])
        query_vectors = extract_embeddings(embedding_response)
        if not query_vectors:
            raise RuntimeError("Voyage embedding response did not include any vectors.")
        query_vector = query_vectors[0]

        # Build the pipeline using the new Atlas Vector Search stage.
        filter_param = build_filter_clause(args)
        vector_search_stage: Dict[str, Any] = {
            "$vectorSearch": {
                "index": settings["index_name"],
                "path": "emb_description",
                "queryVector": query_vector,
                "limit": args.k,
                "numCandidates": max(args.k * 5, 200),
            }
        }
        if filter_param:
            vector_search_stage["$vectorSearch"].update(filter_param)

        pipeline = [
            vector_search_stage,
            {
                "$project": {
                    "_id": 1,
                    "product.name": 1,
                    "restaurantName": 1,
                    "score": {"$meta": "vectorSearchScore"},
                }
            },
        ]

        collection = mongo_client[settings["db_name"]][settings["collection_name"]]
        results = list(collection.aggregate(pipeline))

        if not results:
            print("No matching documents found.")
            return
        print(json.dumps(results, default=str, indent=2))
    finally:
        mongo_client.close()


if __name__ == "__main__":
    main()
