"""Flask application for the AI Blood Bank demo."""
from datetime import datetime, timezone
from functools import wraps
import hmac
import os
import secrets
from urllib.parse import urlsplit

from bson import ObjectId
from bson.errors import InvalidId
from flask import Flask, abort, flash, redirect, render_template, request, session, url_for
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError, PyMongoError

from config import Config
from mongodb import create_mongo_client, get_database
from routes.health_routes import health_bp
from services.auth_service import hash_password, verify_and_upgrade_password
from services.inventory_service import approve_request as approve_request_service
from services.inventory_service import reject_request as reject_request_service
from services.prediction_service import predict_group_demand


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

    @app.get("/")
    def home():
        return render_template("home.html")

    @app.route("/signup", methods=["GET", "POST"])
    def signup():
        if request.method == "POST":
            data = {key: request.form.get(key, "").strip() for key in
                    ("fullname", "email", "phone", "blood_group", "gender")}
            password = request.form.get("password", "")
            try:
                age = int(request.form.get("age", ""))
            except ValueError:
                age = 0
            if not data["fullname"] or "@" not in data["email"] or len(password) < 8:
                flash("Enter your name and a valid email; password must have 8 or more characters.", "danger")
                return render_template("signup.html", form=data), 400
            if data["blood_group"] not in Config.BLOOD_GROUPS or not 18 <= age <= 65:
                flash("Choose a valid blood group and enter an age from 18 to 65.", "danger")
                return render_template("signup.html", form=data), 400
            data.update(email=data["email"].lower(), age=age,
                        password=hash_password(password), role="user",
                        donor=bool(request.form.get("donor")), created_at=datetime.now(timezone.utc))
            try:
                users.insert_one(data)
            except DuplicateKeyError:
                flash("That email is already registered.", "warning")
                return render_template("signup.html", form=data), 409
            flash("Account created. Please sign in.", "success")
            return redirect(url_for("login"))
        return render_template("signup.html")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            user = users.find_one({"email": email})
            password = request.form.get("password", "")
            # Upgrade existing plaintext passwords after a successful sign-in.
            valid = verify_and_upgrade_password(users, user, password)
            if not user or not valid:
                flash("Email or password is incorrect.", "danger")
                return render_template("login.html"), 401
            session.clear()
            session.update(user_id=str(user["_id"]), user=user.get("fullname", "User"),
                           role=user.get("role", "user"))
            destination = request.args.get("next", "")
            parsed = urlsplit(destination)
            if not destination.startswith("/") or destination.startswith("//") or parsed.netloc:
                destination = url_for("dashboard")
            return redirect(destination)
        return render_template("login.html")

    @app.get("/logout")
    def logout():
        session.clear()
        flash("You have signed out.", "success")
        return redirect(url_for("home"))

    @app.get("/dashboard")
    @login_required
    def dashboard():
        total = 0
        for row in inventory.find({}, {"units": 1}):
            try:
                total += max(0, int(row.get("units", 0) or 0))
            except (ValueError, TypeError):
                app.logger.warning("Ignoring invalid inventory units in record %s", row.get("_id"))
        return render_template("dashboard.html", username=session.get("user"), role=session.get("role"),
                               donor_count=users.count_documents({"donor": True}), total_blood_units=total,
                               hospital_count=hospitals.count_documents({}),
                               request_count=requests_col.count_documents({}))

    @app.get("/inventory")
    @login_required
    def inventory_view():
        return render_template("inventory.html", blood_data=list(inventory.find().sort("blood_group", 1)),
                               role=session.get("role"))

    @app.route("/add_blood", methods=["GET", "POST"])
    @app.route("/inventory/add", methods=["GET", "POST"])
    @admin_required
    def add_blood():
        if request.method == "POST":
            group = request.form.get("blood_group", "")
            try:
                units = int(request.form.get("units", ""))
            except ValueError:
                units = -1
            if group not in Config.BLOOD_GROUPS or units < 0:
                flash("Choose a valid blood group and nonnegative unit count.", "danger")
                return render_template("add_blood.html"), 400
            inventory.insert_one({"blood_group": group, "units": units,
                                  "last_updated": request.form.get("last_updated", ""),
                                  "created_at": datetime.now(timezone.utc)})
            return redirect(url_for("inventory_view"))
        return render_template("add_blood.html")

    @app.route("/edit_blood/<id>", methods=["GET", "POST"])
    @admin_required
    def edit_blood(id):
        record_id = oid(id)
        record = inventory.find_one({"_id": record_id})
        if not record:
            abort(404)
        if request.method == "POST":
            group = request.form.get("blood_group", "")
            try:
                units = int(request.form.get("units", ""))
            except ValueError:
                units = -1
            if group not in Config.BLOOD_GROUPS or units < 0:
                flash("Choose a valid blood group and nonnegative unit count.", "danger")
                return render_template("edit_blood.html", blood=record), 400
            inventory.update_one({"_id": record_id}, {"$set": {"blood_group": group, "units": units,
                                 "last_updated": request.form.get("last_updated", ""),
                                 "updated_at": datetime.now(timezone.utc)}})
            return redirect(url_for("inventory_view"))
        return render_template("edit_blood.html", blood=record)

    @app.post("/delete_blood/<id>")
    @admin_required
    def delete_blood(id):
        inventory.delete_one({"_id": oid(id)})
        return redirect(url_for("inventory_view"))

    @app.route("/donate_blood", methods=["GET", "POST"])
    @login_required
    def donate_blood():
        user = current_user()
        if request.method == "POST":
            try:
                age = int(request.form.get("age", ""))
            except ValueError:
                age = 0
            group = request.form.get("blood_group", "")
            if group not in Config.BLOOD_GROUPS or not 18 <= age <= 65:
                flash("Choose a valid blood group and enter an age from 18 to 65.", "danger")
                return render_template("donate_blood.html", user=user), 400
            users.update_one({"_id": ObjectId(session["user_id"])}, {"$set": {
                "fullname": request.form.get("fullname", "").strip(),
                "phone": request.form.get("phone", "").strip(), "blood_group": group, "age": age,
                "gender": request.form.get("gender", ""), "donor": True,
                "donor_registered_at": datetime.now(timezone.utc)}})
            flash("Donor profile saved.", "success")
            return redirect(url_for("dashboard"))
        return render_template("donate_blood.html", user=user)

    @app.route("/request_blood", methods=["GET", "POST"])
    @login_required
    def request_blood():
        if request.method == "POST":
            group = request.form.get("blood_group", "")
            try:
                units = int(request.form.get("units", ""))
            except ValueError:
                units = 0
            if not request.form.get("patient_name", "").strip() or group not in Config.BLOOD_GROUPS or units < 1:
                flash("Enter the patient name, a valid blood group, and at least one unit.", "danger")
                return render_template("request_blood.html", hospitals=list(hospitals.find())), 400
            requests_col.insert_one({"patient_name": request.form["patient_name"].strip(), "blood_group": group,
                "units": units, "hospital": request.form.get("hospital", "").strip(), "status": "Pending",
                "requested_by": session.get("user"), "requested_by_id": session["user_id"],
                "created_at": datetime.now(timezone.utc)})
            return redirect(url_for("view_requests"))
        return render_template("request_blood.html", hospitals=list(hospitals.find()))

    @app.get("/view_requests")
    @login_required
    def view_requests():
        query = {} if session.get("role") == "admin" else {"requested_by_id": session["user_id"]}
        return render_template("view_requests.html", requests_data=list(requests_col.find(query).sort("created_at", -1)),
                               role=session.get("role"))

    @app.get("/request_details/<id>")
    @login_required
    def request_details(id):
        record = requests_col.find_one({"_id": oid(id)})
        if not record:
            abort(404)
        if session.get("role") != "admin" and record.get("requested_by_id") != session.get("user_id"):
            abort(403)
        return render_template("request_details.html", blood_request=record)

    def decide_request(id, status):
        request_id = oid(id)
        record = requests_col.find_one({"_id": request_id})
        if not record:
            abort(404)
        if record.get("status") != "Pending":
            flash("This request has already been reviewed.", "warning")
            return redirect(url_for("view_requests"))
        if status == "Approved":
            result = approve_request_service(inventory, requests_col, record)
            if result == "insufficient_stock":
                flash("Not enough stock is available to approve this request.", "danger")
            elif result == "already_reviewed":
                flash("This request has already been reviewed.", "warning")
        elif not reject_request_service(requests_col, record):
            flash("This request has already been reviewed.", "warning")
        return redirect(url_for("view_requests"))

    @app.post("/approve_request/<id>")
    @admin_required
    def approve_request(id):
        return decide_request(id, "Approved")

    @app.post("/reject_request/<id>")
    @admin_required
    def reject_request(id):
        return decide_request(id, "Rejected")

    @app.get("/hospitals")
    @login_required
    def hospitals_view():
        return render_template("hospitals.html", hospitals_data=list(hospitals.find().sort("name", 1)))

    @app.route("/add_hospital", methods=["GET", "POST"])
    @admin_required
    def add_hospital():
        if request.method == "POST":
            name = request.form.get("name", "").strip()
            if not name:
                flash("Hospital name is required.", "danger")
                return render_template("add_hospital.html"), 400
            hospitals.insert_one({"name": name, "location": request.form.get("location", "").strip(),
                "phone": request.form.get("phone", "").strip(), "connected": True,
                "created_at": datetime.now(timezone.utc)})
            return redirect(url_for("hospitals_view"))
        return render_template("add_hospital.html")

    @app.route("/edit_hospital/<id>", methods=["GET", "POST"])
    @admin_required
    def edit_hospital(id):
        record_id = oid(id)
        hospital = hospitals.find_one({"_id": record_id})
        if not hospital:
            abort(404)
        if request.method == "POST":
            name = request.form.get("name", "").strip()
            if not name:
                flash("Hospital name is required.", "danger")
                return render_template("edit_hospital.html", hospital=hospital), 400
            hospitals.update_one({"_id": record_id}, {"$set": {"name": name,
                "location": request.form.get("location", "").strip(), "phone": request.form.get("phone", "").strip()}})
            return redirect(url_for("hospitals_view"))
        return render_template("edit_hospital.html", hospital=hospital)

    @app.post("/delete_hospital/<id>")
    @admin_required
    def delete_hospital(id):
        hospitals.delete_one({"_id": oid(id)})
        return redirect(url_for("hospitals_view"))

    @app.get("/admin")
    @app.get("/admin/dashboard")
    @admin_required
    def admin_dashboard():
        return render_template("admin_dashboard.html", users_count=users.count_documents({}),
            request_count=requests_col.count_documents({}), donor_count=users.count_documents({"donor": True}),
            hospital_count=hospitals.count_documents({}))

    @app.get("/admin/users")
    @admin_required
    def manage_users():
        return render_template("users.html", users_data=list(users.find({}, {"password": 0}).sort("created_at", -1)))

    @app.post("/admin/users/<id>/role")
    @admin_required
    def update_user_role(id):
        role = request.form.get("role")
        if role not in ("admin", "user"):
            abort(400)
        if str(oid(id)) == session.get("user_id") and role != "admin":
            flash("You cannot remove your own administrator access.", "warning")
        else:
            users.update_one({"_id": oid(id)}, {"$set": {"role": role}})
        return redirect(url_for("manage_users"))

    @app.post("/admin/users/<id>/delete")
    @admin_required
    def delete_user(id):
        user_id = oid(id)
        if str(user_id) == session.get("user_id"):
            abort(400)
        users.delete_one({"_id": user_id})
        return redirect(url_for("manage_users"))

    @app.get("/admin/donors")
    @admin_required
    def manage_donors():
        return render_template("donors.html", donors_data=list(users.find({"donor": True}, {"password": 0})), is_admin=True)

    @app.get("/donors")
    @login_required
    def donor_directory():
        return render_template("donor_directory.html", donors_data=list(users.find(
            {"donor": True}, {"fullname": 1, "blood_group": 1})), is_admin=False)

    @app.get("/admin/donors/<id>")
    @admin_required
    def donor_details(id):
        donor = users.find_one({"_id": oid(id), "donor": True}, {"password": 0})
        if not donor:
            abort(404)
        return render_template("donor_details.html", donor=donor)

    @app.post("/admin/donors/<id>/remove")
    @admin_required
    def remove_donor_status(id):
        users.update_one({"_id": oid(id), "donor": True}, {"$set": {"donor": False}})
        return redirect(url_for("manage_donors"))

    @app.route("/ai_prediction", methods=["GET", "POST"])
    @app.route("/prediction", methods=["GET", "POST"])
    @login_required
    def ai_prediction():
        result = None
        if request.method == "POST":
            group = request.form.get("blood_group", "")
            if group not in Config.BLOOD_GROUPS:
                abort(400)
            result = predict_group_demand(list(requests_col.find({"blood_group": group}, {"created_at": 1})), group)
            predictions.insert_one({**result, "blood_group": group, "created_at": datetime.now(timezone.utc),
                                    "requested_by_id": session["user_id"]})
        return render_template("prediction.html", result=result, blood_groups=Config.BLOOD_GROUPS)

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
