from __future__ import annotations

from flask import Blueprint, jsonify

from .db import get_collection

api_bp = Blueprint("api", __name__, url_prefix="/api")


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
