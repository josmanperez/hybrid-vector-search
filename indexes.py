import argparse
import os
from typing import Any, Dict

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import OperationFailure


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create MongoDB search & vector indexes for the product detail collection.")
    parser.add_argument(
        "--num-dimensions",
        type=int,
        default=int(os.getenv("VECTOR_INDEX_DIMENSIONS")) if os.getenv("VECTOR_INDEX_DIMENSIONS") else None,
        help="Explicit number of dimensions for the embedding vectors.",
    )
    parser.add_argument(
        "--name",
        default=os.getenv("VECTOR_INDEX_NAME") or os.getenv("ATLAS_SEARCH_INDEX", "products_vector_index"),
        help="Name of the vector search index to create.",
    )
    parser.add_argument(
        "--similarity",
        default=os.getenv("VECTOR_INDEX_SIMILARITY", "cosine"),
        choices=["cosine", "dotProduct", "euclidean"],
        help="Similarity metric for the vector search index.",
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Drop the existing index with the same name before creating a new one.",
    )
    return parser.parse_args()


def load_settings() -> Dict[str, str]:
    load_dotenv()
    mongo_uri = os.getenv("MONGODB_URI")
    db_name = os.getenv("DB_NAME")
    collection_name = os.getenv("PRODUCT_DETAIL_COLLECTION") or os.getenv("COLLECTION_NAME")

    missing = [name for name, value in [("MONGODB_URI", mongo_uri), ("DB_NAME", db_name), ("COLLECTION_NAME", collection_name)] if not value]
    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")

    return {"mongo_uri": mongo_uri, "db_name": db_name, "collection_name": collection_name}


def build_index_definitions(name: str, num_dimensions: int, similarity: str) -> list[Dict[str, Any]]:
    vector_index = {
        "name": name,
        "type": "vectorSearch",
        "definition": {
            "fields": [
                {
                    "type": "vector",
                    "path": "emb_description",
                    "numDimensions": num_dimensions,
                    "similarity": similarity,
                },
                {"type": "filter", "path": "product.available"},
                {"type": "filter", "path": "product.price.amount"},
                {"type": "filter", "path": "restaurantName"},
            ]
        },
    }

    full_text_index = {
        "name": "full-text-search",
        "type": "search",
        "definition": {
            "mappings": {
                "dynamic": False,
                "fields": {
                    "title": {
                        "type": "string",
                    }
                },
            }
        },
    }

    return [vector_index, full_text_index]


def main() -> None:
    args = parse_args()
    settings = load_settings()

    num_dimensions = args.num_dimensions if args.num_dimensions is not None else 0
    if num_dimensions <= 0:
        raise ValueError("numDimensions must be a positive integer.")

    index_definitions = build_index_definitions(args.name, num_dimensions, args.similarity)

    client = MongoClient(settings["mongo_uri"])
    try:
        collection = client[settings["db_name"]][settings["collection_name"]]

        for definition in index_definitions:
            index_name = definition["name"]

            if args.replace:
                try:
                    collection.drop_search_index(index_name)
                    print(f"[INFO] Dropped existing index '{index_name}'.")
                except OperationFailure as exc:
                    if exc.code == 27 or "index not found" in str(exc).lower():
                        print(f"[INFO] No existing index named '{index_name}' to drop.")
                    else:
                        raise

            result = collection.create_search_index(definition)
            print(f"[OK] Created search index '{index_name}'. Response: {result}")
    finally:
        client.close()


if __name__ == "__main__":
    main()
