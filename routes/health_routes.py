"""Operational health endpoint."""
from flask import Blueprint, current_app

health_bp = Blueprint("health", __name__)


@health_bp.get("/health")
def health():
    try:
        current_app.extensions["mongo_db"].command("ping")
        return {"status": "ok", "database": "connected"}
    except Exception:
        current_app.logger.exception("MongoDB health check failed")
        return {"status": "unavailable", "database": "disconnected"}, 503
