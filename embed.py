import argparse
import os
from typing import Dict, List, Tuple

from dotenv import load_dotenv
from pymongo import MongoClient
from voyageai import Client

from utils.logger import get_logger


def parse_args() -> argparse.Namespace:
    load_dotenv()
    parser = argparse.ArgumentParser(
        description="Embed product descriptions in the product_detail collection using VoyageAI."
    )
    parser.add_argument(
        "--collection",
        default=os.getenv("PRODUCT_DETAIL_COLLECTION", "product_detail"),
        help="MongoDB collection containing product-level documents (default: product_detail).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Maximum number of documents to process.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=16,
        help="Number of descriptions to embed per VoyageAI request (default: 16).",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip documents that already contain an emb_description field.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview updates without writing to MongoDB.",
    )
    return parser.parse_args()


def load_settings() -> Dict[str, str]:
    load_dotenv()
    mongo_uri = os.getenv("MONGODB_URI")
    db_name = os.getenv("DB_NAME")
    api_key = os.getenv("VOYAGE_API_KEY")
    text_model = os.getenv("VOYAGE_TEXT_MODEL", "voyage-3.5")

    missing = [
        name
        for name, value in [
            ("MONGODB_URI", mongo_uri),
            ("DB_NAME", db_name),
            ("VOYAGE_API_KEY", api_key),
        ]
        if not value
    ]
    if missing:
        raise RuntimeError(
            f"Missing required environment variables: {', '.join(missing)}"
        )

    return {
        "mongo_uri": mongo_uri,
        "db_name": db_name,
        "api_key": api_key,
        "text_model": text_model,
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


def batched(iterable: List[Tuple[Dict, str]], size: int) -> List[List[Tuple[Dict, str]]]:
    return [iterable[i : i + size] for i in range(0, len(iterable), size)]


def collect_documents(cursor, skip_existing: bool) -> List[Tuple[Dict, str]]:
    collected: List[Tuple[Dict, str]] = []
    for document in cursor:
        if skip_existing and "emb_description" in document:
            continue
        description = (
            document.get("product", {}).get("description")
            if isinstance(document.get("product"), dict)
            else None
        )
        if isinstance(description, str) and description.strip():
            collected.append((document, description.strip()))
    return collected


def main() -> None:
    args = parse_args()
    settings = load_settings()

    logger = get_logger("embed")

    voyage_client = Client(api_key=settings["api_key"])
    mongo_client = MongoClient(settings["mongo_uri"])

    try:
        collection = mongo_client[settings["db_name"]][args.collection]
        cursor = collection.find({})
        if args.limit:
            cursor = cursor.limit(args.limit)

        documents = collect_documents(cursor, args.skip_existing)
        if not documents:
            logger.info("No product descriptions found to embed.")
            return

        logger.info(
            "Preparing to embed %d product descriptions (batch size=%d, dry_run=%s).",
            len(documents),
            args.batch_size,
            args.dry_run,
        )

        processed = 0
        for batch in batched(documents, args.batch_size):
            ids = [doc["_id"] for doc, _ in batch]
            descriptions = [text for _, text in batch]
            if args.dry_run:
                logger.info(
                    "[DRY-RUN] Would embed and update documents: %s",
                    ", ".join(str(_id) for _id in ids),
                )
                processed += len(batch)
                continue

            response = voyage_client.embed(texts=descriptions, model=settings["text_model"])
            embeddings = extract_embeddings(response)

            for (doc, _), vector in zip(batch, embeddings):
                collection.update_one(
                    {"_id": doc["_id"]},
                    {"$set": {"emb_description": vector}},
                )

            processed += len(batch)
            logger.info(
                "Embedded and updated %d/%d documents.", processed, len(documents)
            )

        if args.dry_run:
            logger.info("[DRY-RUN] Finished simulation for %d documents.", processed)
        else:
            logger.info("Embedded descriptions for %d documents.", processed)
    finally:
        mongo_client.close()


if __name__ == "__main__":
    main()
