"""
Flask application factory.
"""

import os

from dotenv import load_dotenv
from flask import Flask, send_from_directory
from flask_cors import CORS

from app.api.routes import api
from app.models.database import init_db


def create_app():
    load_dotenv()

    # Serve the built React frontend from ../frontend/dist
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    static_folder = os.path.join(base_dir, "..", "frontend", "dist")

    app = Flask(__name__, static_folder=static_folder, static_url_path="")
    app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key")

    # File storage paths
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

    # CORS - allow all origins for container environments
    CORS(app)

    # Register API blueprint
    app.register_blueprint(api)

    # Health check endpoint
    @app.route("/health")
    def health():
        return {"status": "ok"}

    # Serve React app for all non-API routes (SPA routing)
    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def serve_frontend(path):
        # If the file exists in dist/, serve it
        if path and os.path.exists(os.path.join(app.static_folder, path)):
            return send_from_directory(app.static_folder, path)
        # Otherwise serve index.html (React SPA handles routing)
        return send_from_directory(app.static_folder, "index.html")

    # Initialize database
    with app.app_context():
        init_db()

    return app
