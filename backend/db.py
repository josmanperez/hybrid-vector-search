from __future__ import annotations

from flask import current_app, g
from pymongo import MongoClient


def get_db():
    if "mongo_client" not in g:
        mongo_uri = current_app.config.get("MONGO_URI")
        if not mongo_uri:
            raise RuntimeError("MongoDB URI not configured on the Flask application.")
        g.mongo_client = MongoClient(mongo_uri)
    db_name = current_app.config.get("DB_NAME")
    if not db_name:
        raise RuntimeError("Database name not configured on the Flask application.")
    return g.mongo_client[db_name]


def get_collection(name: str | None = None):
    collection_name = name or current_app.config.get("PRODUCT_COLLECTION")
    if not collection_name:
        raise RuntimeError("Collection name not configured on the Flask application.")
    return get_db()[collection_name]


def close_db(_=None):
    mongo_client = g.pop("mongo_client", None)
    if mongo_client is not None:
        mongo_client.close()
