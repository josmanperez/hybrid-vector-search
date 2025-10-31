from __future__ import annotations

import os

from dotenv import load_dotenv
from flask import Flask, render_template

from backend.api import api_bp
from backend.db import close_db


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

    app.register_blueprint(api_bp)
    app.teardown_appcontext(close_db)

    @app.route("/")
    def index():
        return render_template("index.html")

    return app


if __name__ == "__main__":
    flask_app = create_app()
    flask_app.run(debug=True)
