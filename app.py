from __future__ import annotations

import os

from dotenv import load_dotenv
from flask import Flask, render_template

from backend.api import api_bp
from backend.db import close_db
from backend.voyage import close_client


def create_app() -> Flask:
    load_dotenv()
    app = Flask(
        __name__,
        template_folder="frontend/templates",
        static_folder="frontend/static",
    )

    app.config["MONGO_URI"] = os.getenv("MONGODB_URI")
    app.config["DB_NAME"] = os.getenv("DB_NAME")
    app.config["PRODUCT_COLLECTION"] = os.getenv("PRODUCT_DETAIL_COLLECTION", "product_detail")
    app.config["VOYAGE_API_KEY"] = os.getenv("VOYAGE_API_KEY")
    app.config["VOYAGE_TEXT_MODEL"] = os.getenv("VOYAGE_TEXT_MODEL", "voyage-3.5")
    app.config["VECTOR_INDEX_NAME"] = os.getenv("VECTOR_INDEX_NAME") or os.getenv("ATLAS_SEARCH_INDEX")
    app.config["ATLAS_SEARCH_INDEX"] = os.getenv("ATLAS_SEARCH_INDEX")
    app.config["FULL_TEXT_INDEX_NAME"] = os.getenv("FULL_TEXT_INDEX_NAME", "full-text-search")

    app.register_blueprint(api_bp)
    app.teardown_appcontext(close_db)
    app.teardown_appcontext(close_client)

    @app.route("/")
    def index():
        return render_template("index.html")

    return app


if __name__ == "__main__":
    flask_app = create_app()
    flask_app.run(debug=True)
