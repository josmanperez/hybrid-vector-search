from __future__ import annotations

from flask import current_app, g
from voyageai import Client


def get_client() -> Client:
    if "voyage_client" not in g:
        api_key = current_app.config.get("VOYAGE_API_KEY")
        if not api_key:
            raise RuntimeError("VoyageAI API key not configured on the Flask application.")
        g.voyage_client = Client(api_key=api_key)
    return g.voyage_client


def close_client(_=None):
    client = g.pop("voyage_client", None)
    if client and hasattr(client, "close"):
        client.close()
