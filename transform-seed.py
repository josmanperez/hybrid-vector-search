import argparse
import os
from typing import Dict, Iterable, List

from bson import ObjectId
from dotenv import load_dotenv
from pymongo import MongoClient

from utils.logger import get_logger


def parse_args() -> argparse.Namespace:
    load_dotenv()
    parser = argparse.ArgumentParser(
        description="Transform catalog documents by unwinding products into a flattened collection."
    )
    parser.add_argument(
        "--source",
        default=os.getenv("COLLECTION_NAME", "products"),
        help="Source collection containing catalog documents (default: value of COLLECTION_NAME env var).",
    )
    parser.add_argument(
        "--target",
        default=os.getenv("PRODUCT_DETAIL_COLLECTION", "product_detail"),
        help="Target collection to store product-level documents (default: product_detail).",
    )
    parser.add_argument(
        "--drop-target",
        action="store_true",
        help="Drop the target collection before inserting transformed documents.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Optional limit of source documents to process before transforming.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=500,
        help="Number of documents to insert per batch (default: 500).",
    )
    return parser.parse_args()


def load_settings() -> Dict[str, str]:
    load_dotenv()
    mongo_uri = os.getenv("MONGODB_URI")
    db_name = os.getenv("DB_NAME")

    missing = [
        name
        for name, value in [("MONGODB_URI", mongo_uri), ("DB_NAME", db_name)]
        if not value
    ]
    if missing:
        raise RuntimeError(
            f"Missing required environment variables: {', '.join(missing)}"
        )

    return {"mongo_uri": mongo_uri, "db_name": db_name}


def iter_products(document: dict) -> Iterable[dict]:
    products = document.get("products", [])
    if not isinstance(products, list):
        return []
    return [product for product in products if isinstance(product, dict)]


def build_product_document(source: dict, product: dict) -> dict:
    base = {
        key: value
        for key, value in source.items()
        if key not in {"products", "description_embeddings", "image_embeddings"}
    }

    catalog_id = source.get("_id")
    if catalog_id is not None:
        base["catalogId"] = catalog_id

    product_id = product.get("_id")
    if isinstance(product_id, ObjectId):
        base["_id"] = product_id
    elif isinstance(product_id, str):
        try:
            base["_id"] = ObjectId(product_id)
        except Exception:
            base["_id"] = ObjectId()
    else:
        base["_id"] = ObjectId()

    base["product"] = product
    return base


def main() -> None:
    args = parse_args()
    settings = load_settings()

    logger = get_logger("transform")

    client = MongoClient(settings["mongo_uri"])
    try:
        db = client[settings["db_name"]]
        source_collection = db[args.source]
        target_collection = db[args.target]

        if args.drop_target:
            target_collection.drop()
            logger.info("Dropped target collection '%s'.", args.target)

        cursor = source_collection.find({})
        if args.limit:
            cursor = cursor.limit(args.limit)

        batch: List[dict] = []
        total_products = 0
        total_documents = 0

        for document in cursor:
            total_documents += 1
            for product in iter_products(document):
                batch.append(build_product_document(document, product))
                total_products += 1

                if len(batch) >= args.batch_size:
                    target_collection.insert_many(batch)
                    batch.clear()
                    logger.info(
                        "Inserted %d product documents so far into '%s'.",
                        total_products,
                        args.target,
                    )

        if batch:
            target_collection.insert_many(batch)
            logger.info(
                "Inserted remaining %d product documents into '%s'.",
                len(batch),
                args.target,
            )

        logger.info(
            "Processed %d source documents and generated %d product documents into '%s'.",
            total_documents,
            total_products,
            args.target,
        )
    finally:
        client.close()


if __name__ == "__main__":
    main()
