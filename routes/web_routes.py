"""Application HTTP routes; authentication and business rules use services."""
from datetime import datetime, timezone
import os
from pathlib import Path
from uuid import uuid4
from urllib.parse import urlsplit

from PIL import Image, UnidentifiedImageError
from flask import current_app
from bson import ObjectId
from flask import abort, flash, redirect, render_template, request, session, url_for
from pymongo.errors import DuplicateKeyError

from config import Config
from services.auth_service import hash_password, verify_and_upgrade_password
from services.inventory_service import approve_request as approve_request_service
from services.inventory_service import reject_request as reject_request_service
from services.prediction_service import predict_group_demand


def register_web_routes(app, mongo_database, login_required, admin_required, oid, current_user):
    users = mongo_database["users"]
    inventory = mongo_database["blood_inventory"]
    requests_col = mongo_database["requests"]
    hospitals = mongo_database["hospitals"]
    predictions = mongo_database["predictions"]

    @app.get("/")
    def home():
        return render_template("home.html")

    
    @app.route("/signup", methods=["GET", "POST"])
    def signup():
        if request.method == "POST":
            data = {
                key: request.form.get(key, "").strip()
                for key in (
                    "fullname",
                    "email",
                    "phone",
                    "blood_group",
                    "gender",
                )
            }

            password = request.form.get("password", "")
            confirm_password = request.form.get("confirm_password", "")

            # Validate age
            try:
                age = int(request.form.get("age", ""))
            except (ValueError, TypeError):
                age = 0

            # Validate name, email, and password
            if (
                not data["fullname"]
                or "@" not in data["email"]
                or len(password) < 8
            ):
                flash(
                    "Enter your name and a valid email; password must have at least 8 characters.",
                    "danger",
                )
                return render_template("signup.html", form=data), 400

            # Validate password confirmation
            if password != confirm_password:
                flash(
                    "The password and confirmation do not match.",
                    "danger",
                )
                return render_template("signup.html", form=data), 400

            # Validate gender selection
            if data["gender"] not in (
                "Female",
                "Male",
                "Other",
                "Prefer not to say",
            ):
                flash("Please choose a valid gender option.", "danger")
                return render_template("signup.html", form=data), 400

            # Validate blood group and age
            if (
                data["blood_group"] not in Config.BLOOD_GROUPS
                or not 18 <= age <= 65
            ):
                flash(
                    "Choose a valid blood group and enter an age from 18 to 65.",
                    "danger",
                )
                return render_template("signup.html", form=data), 400

            # Normalize email
            data["email"] = data["email"].lower()

            # Check whether the email is already registered
            if users.find_one({"email": data["email"]}):
                flash("That email is already registered.", "warning")
                return render_template("signup.html", form=data), 409

            # Prepare the user document
            data.update(
                age=age,
                password=hash_password(password),
                role="user",
                donor=bool(request.form.get("donor")),
                created_at=datetime.now(timezone.utc),
            )

            # Save the new user in MongoDB
            try:
                users.insert_one(data)
            except DuplicateKeyError:
                flash("That email is already registered.", "warning")
                return render_template("signup.html", form=data), 409

            flash("Account created successfully. Please sign in.", "success")
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


    @app.route("/forgot-password", methods=["GET", "POST"])
    def forgot_password():
        # LOCAL DEMO ONLY: show the temporary reset link on screen; no email is sent.
        import hashlib
        import secrets
        from datetime import timedelta

        demo_reset_link = None
        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            user = users.find_one({"email": email}) if email else None
            if user:
                token = secrets.token_urlsafe(32)
                token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
                expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)
                users.update_one({"_id": user["_id"]}, {"$set": {
                    "reset_token_hash": token_hash,
                    "reset_token_expires_at": expires_at,
                }})
                demo_reset_link = url_for("reset_password", token=token)
            else:
                flash("If that email belongs to an account, a reset link would be generated in this local demo.", "info")
        return render_template("forgot_password.html", demo_reset_link=demo_reset_link)

    @app.route("/reset-password/<token>", methods=["GET", "POST"])
    def reset_password(token):
        import hashlib
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        query = {
            "reset_token_hash": token_hash,
            "reset_token_expires_at": {"$gt": datetime.now(timezone.utc)},
        }
        user = users.find_one(query)
        if not user:
            flash("This reset link is invalid, expired, or already used. Generate a new demo link.", "danger")
            return render_template("reset_password.html", token=token, valid_token=False), 400
        if request.method == "POST":
            password = request.form.get("password", "")
            confirm = request.form.get("confirm_password", "")
            if len(password) < 8:
                flash("Password must contain at least 8 characters.", "danger")
            elif password != confirm:
                flash("The passwords do not match.", "danger")
            else:
                users.update_one({"_id": user["_id"], "reset_token_hash": token_hash}, {
                    "$set": {"password": hash_password(password)},
                    "$unset": {"reset_token_hash": "", "reset_token_expires_at": ""},
                })
                flash("Password updated. Please sign in with your new password.", "success")
                return redirect(url_for("login"))
        return render_template("reset_password.html", token=token, valid_token=True)

    @app.route("/profile", methods=["GET", "POST"])
    @login_required
    def profile():
        user = current_user()
        if not user:
            session.clear()
            flash("Please sign in again.", "warning")
            return redirect(url_for("login"))

        if request.method == "POST":
            fullname = request.form.get("fullname", "").strip()
            email = request.form.get("email", "").strip().lower()
            phone = request.form.get("phone", "").strip()
            blood_group = request.form.get("blood_group", "").strip()
            gender = request.form.get("gender", "").strip()
            try:
                age = int(request.form.get("age", ""))
            except (TypeError, ValueError):
                age = 0
            donor = request.form.get("donor") == "on"
            values = {**user, "fullname": fullname, "email": email, "phone": phone,
                      "blood_group": blood_group, "gender": gender, "age": age, "donor": donor}

            if not fullname or "@" not in email or len(email) > 254:
                flash("Enter your full name and a valid email address.", "danger")
                return render_template("profile.html", user=values), 400
            if blood_group not in Config.BLOOD_GROUPS or not 18 <= age <= 65:
                flash("Choose a valid blood group and enter an age from 18 to 65.", "danger")
                return render_template("profile.html", user=values), 400
            if len(phone) > 30 or len(gender) > 40:
                flash("Phone or gender field is too long.", "danger")
                return render_template("profile.html", user=values), 400
            if users.find_one({"email": email, "_id": {"$ne": user["_id"]}}):
                flash("That email address is already used by another account.", "warning")
                return render_template("profile.html", user=values), 409

            users.update_one({"_id": user["_id"]}, {"$set": {
                "fullname": fullname, "email": email, "phone": phone,
                "blood_group": blood_group, "age": age, "gender": gender, "donor": donor,
            }})
            session["user"] = fullname
            flash("Your profile has been updated.", "success")
            return redirect(url_for("profile"))
        return render_template("profile.html", user=user)
    @app.post("/profile/picture")
    @login_required
    def update_profile_picture():
        user = current_user()
        if not user:
            session.clear()
            flash("Please sign in again.", "warning")
            return redirect(url_for("login"))

        uploaded = request.files.get("profile_picture")
        if not uploaded or not uploaded.filename:
            flash("Choose a picture to upload.", "warning")
            return redirect(url_for("profile"))

        # Limit uploads to 5 MB.
        uploaded.stream.seek(0, os.SEEK_END)
        file_size = uploaded.stream.tell()
        uploaded.stream.seek(0)

        if file_size > 5 * 1024 * 1024:
            flash("The picture must be 5 MB or smaller.", "danger")
            return redirect(url_for("profile"))

        try:
            image = Image.open(uploaded.stream)
            if image.format not in ("JPEG", "PNG", "WEBP"):
                raise ValueError("Unsupported image format.")
            image.verify()

            uploaded.stream.seek(0)
            image = Image.open(uploaded.stream)
            image.load()
        except (UnidentifiedImageError, OSError, ValueError):
            flash("Upload a valid JPG, PNG, or WebP image.", "danger")
            return redirect(url_for("profile"))

        upload_dir = Path(current_app.root_path) / "static" / "uploads"
        upload_dir.mkdir(parents=True, exist_ok=True)

        extension = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}[image.format]
        filename = f"{uuid4().hex}{extension}"
        save_path = upload_dir / filename

        # Re-encode the image to avoid saving untrusted original file bytes.
        try:
            if image.mode not in ("RGB", "RGBA"):
                image = image.convert("RGB")
            image.save(save_path, format=image.format if image.format in ("JPEG", "PNG", "WEBP") else "JPEG")
        except (OSError, ValueError):
            save_path.unlink(missing_ok=True)
            flash("The picture could not be saved. Please try another image.", "danger")
            return redirect(url_for("profile"))

        old_filename = user.get("profile_picture")
        users.update_one(
            {"_id": user["_id"]},
            {"$set": {"profile_picture": filename}}
        )

        if old_filename and old_filename != filename:
            old_path = upload_dir / Path(old_filename).name
            if old_path.is_file():
                old_path.unlink(missing_ok=True)

        flash("Profile picture updated.", "success")
        return redirect(url_for("profile"))

    @app.post("/profile/picture/remove")
    @login_required
    def remove_profile_picture():
        user = current_user()
        if not user:
            session.clear()
            flash("Please sign in again.", "warning")
            return redirect(url_for("login"))

        filename = user.get("profile_picture")
        users.update_one(
            {"_id": user["_id"]},
            {"$unset": {"profile_picture": ""}}
        )

        if filename:
            upload_dir = Path(current_app.root_path) / "static" / "uploads"
            old_path = upload_dir / Path(filename).name
            if old_path.is_file():
                old_path.unlink(missing_ok=True)

        flash("Profile picture removed.", "success")
        return redirect(url_for("profile"))


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
        if not user:
            session.clear()
            flash("Please sign in again.", "warning")
            return redirect(url_for("login"))

        if request.method == "POST":
            fullname = request.form.get("fullname", "").strip()
            phone = request.form.get("phone", "").strip()
            group = request.form.get("blood_group", "").strip()
            gender = request.form.get("gender", "").strip()

            try:
                age = int(request.form.get("age", ""))
            except (TypeError, ValueError):
                age = 0

            valid_genders = (
                "Female",
                "Male",
                "Other",
                "Prefer not to say",
            )

            form_user = {
                **user,
                "fullname": fullname,
                "phone": phone,
                "blood_group": group,
                "age": age,
                "gender": gender,
            }

            if not fullname:
                flash("Enter your full name.", "danger")
                return render_template("donate_blood.html", user=form_user), 400

            if len(fullname) > 120 or len(phone) > 30:
                flash("Name or phone field is too long.", "danger")
                return render_template("donate_blood.html", user=form_user), 400

            if group not in Config.BLOOD_GROUPS or not 18 <= age <= 65:
                flash(
                    "Choose a valid blood group and enter an age from 18 to 65.",
                    "danger",
                )
                return render_template("donate_blood.html", user=form_user), 400

            if gender not in valid_genders:
                flash("Please choose a valid gender option.", "danger")
                return render_template("donate_blood.html", user=form_user), 400

            users.update_one(
                {"_id": ObjectId(session["user_id"])},
                {
                    "$set": {
                        "fullname": fullname,
                        "phone": phone,
                        "blood_group": group,
                        "age": age,
                        "gender": gender,
                        "donor": True,
                        "donor_registered_at": datetime.now(timezone.utc),
                    }
                },
            )

            session["user"] = fullname
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
    @app.post("/delete_request/<id>")
    @admin_required
    def delete_request(id):
        request_id = oid(id)
        record = requests_col.find_one({"_id": request_id})

        if not record:
            abort(404)

        requests_col.delete_one({"_id": request_id})
        flash("Blood request deleted.", "success")
        return redirect(url_for("view_requests"))


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

