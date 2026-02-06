"""
Flask application factory.
"""

import os

from dotenv import load_dotenv
from flask import Flask
from flask_cors import CORS

from app.api.routes import api
from app.models.database import init_db


def create_app():
    load_dotenv()

    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key")

    # File storage paths
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    app.config["UPLOAD_FOLDER"] = os.path.join(
        base_dir, os.environ.get("UPLOAD_FOLDER", "uploads")
    )
    app.config["OUTPUT_FOLDER"] = os.path.join(
        base_dir, os.environ.get("OUTPUT_FOLDER", "output")
    )
    app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50MB max upload

    # Ensure directories exist
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    os.makedirs(app.config["OUTPUT_FOLDER"], exist_ok=True)

    # CORS for React frontend
    CORS(app, origins=["http://localhost:5173", "http://localhost:3000"])

    # Register API blueprint
    app.register_blueprint(api)

    # Health check endpoint
    @app.route("/health")
    def health():
        return {"status": "ok"}

    # Initialize database
    with app.app_context():
        init_db()

    return app
