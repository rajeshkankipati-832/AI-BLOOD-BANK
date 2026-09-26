"""Flask application for the AI Blood Bank demo."""
from functools import wraps
import hmac
import os
import secrets

from bson import ObjectId
from bson.errors import InvalidId
from flask import Flask, abort, flash, redirect, render_template, request, session, url_for
from pymongo.errors import PyMongoError

from config import Config
from mongodb import create_mongo_client, get_database
from routes.health_routes import health_bp
from routes.web_routes import register_web_routes


def create_app(test_config=None, mongo_database=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)

    client = None
    if mongo_database is None:
        client = create_mongo_client(app.config["MONGO_URI"])
        mongo_database = get_database(client, app.config["MONGO_DB"])
    app.extensions["mongo_client"] = client
    app.extensions["mongo_db"] = mongo_database

    users = mongo_database["users"]
    inventory = mongo_database["blood_inventory"]
    requests_col = mongo_database["requests"]
    hospitals = mongo_database["hospitals"]
    predictions = mongo_database["predictions"]
    app.register_blueprint(health_bp)

    @app.context_processor
    def csrf_context():
        def csrf_token():
            return session.setdefault("_csrf_token", secrets.token_urlsafe(32))
        return {"csrf_token": csrf_token}

    @app.before_request
    def protect_state_changes():
        if request.method == "POST" and app.config.get("CSRF_ENABLED", True):
            expected = session.get("_csrf_token", "")
            provided = request.form.get("_csrf_token", "")
            if not expected or not hmac.compare_digest(expected, provided):
                abort(400, description="Invalid or missing form security token.")

    def login_required(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not session.get("user_id"):
                flash("Please sign in to continue.", "warning")
                return redirect(url_for("login", next=request.path))
            return view(*args, **kwargs)
        return wrapped

    def admin_required(view):
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            if session.get("role") != "admin":
                abort(403)
            return view(*args, **kwargs)
        return wrapped

    def oid(value):
        try:
            return ObjectId(value)
        except (InvalidId, TypeError):
            abort(404)

    def current_user():
        try:
            return users.find_one({"_id": ObjectId(session["user_id"])})
        except (KeyError, InvalidId):
            return None

    register_web_routes(app, mongo_database, login_required, admin_required, oid, current_user)

    @app.errorhandler(403)
    def forbidden(_error):
        return render_template("error.html", code=403, message="You do not have permission to view this page."), 403

    @app.errorhandler(400)
    def bad_request(_error):
        return render_template("error.html", code=400, message="The request could not be accepted. Refresh the page and try again."), 400

    @app.errorhandler(404)
    def not_found(_error):
        return render_template("404.html"), 404

    @app.errorhandler(PyMongoError)
    def database_error(_error):
        app.logger.exception("Database operation failed")
        return render_template("error.html", code=503, message="The database is unavailable. Please try again."), 503

    @app.errorhandler(500)
    def internal_error(_error):
        return render_template("error.html", code=500, message="Something went wrong. Please try again."), 500

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=os.getenv("FLASK_DEBUG", "false").lower() == "true")
