from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash
import os
import secrets

app = Flask(__name__)

# =========================================================
# CONFIGURATION
# =========================================================

app.secret_key = os.getenv("SECRET_KEY") or secrets.token_hex(32)

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///bloodbank.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


# =========================================================
# USER MODEL
# =========================================================

class User(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    fullname = db.Column(db.String(100), nullable=False)

    email = db.Column(db.String(120), unique=True, nullable=False)

    phone = db.Column(db.String(20))

    blood_group = db.Column(db.String(5))

    age = db.Column(db.Integer)

    gender = db.Column(db.String(20))

    password = db.Column(db.String(255))

    donor = db.Column(db.Boolean, default=False)


# =========================================================
# BLOOD INVENTORY MODEL
# =========================================================

class BloodInventory(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    blood_group = db.Column(db.String(5), nullable=False)

    units = db.Column(db.Integer, nullable=False)

    last_updated = db.Column(db.String(30))


# =========================================================
# BLOOD REQUEST MODEL
# =========================================================

class BloodRequest(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    patient_name = db.Column(db.String(100))

    blood_group = db.Column(db.String(5))

    units = db.Column(db.Integer)

    hospital = db.Column(db.String(100))

    status = db.Column(db.String(30), default="Pending")


# =========================================================
# HOME
# =========================================================

@app.route("/")
def home():

    return render_template("home.html")


# =========================================================
# SIGNUP
# =========================================================

@app.route("/signup", methods=["GET", "POST"])
def signup():

    if request.method == "POST":

        fullname = request.form["fullname"]

        email = request.form["email"]

        phone = request.form["phone"]

        blood_group = request.form["blood_group"]

        age = request.form["age"]

        gender = request.form["gender"]

        password = request.form["password"]

        donor = True if request.form.get("donor") else False

        existing_user = User.query.filter_by(email=email).first()

        if existing_user:

            return "Email already registered."

        new_user = User(
            fullname=fullname,
            email=email,
            phone=phone,
            blood_group=blood_group,
            age=int(age),
            gender=gender,
            password=generate_password_hash(password),
            donor=donor
        )

        db.session.add(new_user)

        db.session.commit()

        return redirect(url_for("login"))

    return render_template("signup.html")


# =========================================================
# LOGIN
# =========================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form["email"]

        password = request.form["password"]

        user = User.query.filter_by(email=email).first()

        valid_password = False
        if user:
            try:
                valid_password = check_password_hash(user.password or "", password)
            except ValueError:
                valid_password = False
            if not valid_password and user.password == password:
                user.password = generate_password_hash(password)
                db.session.commit()
                valid_password = True

        if user and valid_password:

            session["user"] = user.fullname

            session["user_id"] = user.id

            return redirect(url_for("dashboard"))

        return "Invalid Email or Password"

    return render_template("login.html")


# =========================================================
# DASHBOARD
# =========================================================

@app.route("/dashboard")
def dashboard():

    if "user" not in session:

        return redirect(url_for("login"))

    return render_template(
        "dashboard.html",
        username=session["user"]
    )


# =========================================================
# BLOOD INVENTORY
# =========================================================

@app.route("/inventory")
def inventory():

    if "user" not in session:

        return redirect(url_for("login"))

    blood_data = BloodInventory.query.all()

    return render_template(
        "inventory.html",
        blood_data=blood_data
    )


# =========================================================
# ADD BLOOD STOCK
# =========================================================

@app.route("/add_blood", methods=["GET", "POST"])
def add_blood():

    if "user" not in session:

        return redirect(url_for("login"))

    if request.method == "POST":

        blood_group = request.form["blood_group"]

        units = request.form["units"]

        last_updated = request.form["last_updated"]

        stock = BloodInventory(
            blood_group=blood_group,
            units=int(units),
            last_updated=last_updated
        )

        db.session.add(stock)

        db.session.commit()

        return redirect(url_for("inventory"))

    return render_template("add_blood.html")


# =========================================================
# EDIT BLOOD STOCK
# =========================================================

@app.route("/edit_blood/<int:id>", methods=["GET", "POST"])
def edit_blood(id):

    if "user" not in session:

        return redirect(url_for("login"))

    blood = BloodInventory.query.get_or_404(id)

    if request.method == "POST":

        blood.blood_group = request.form["blood_group"]

        blood.units = int(request.form["units"])

        blood.last_updated = request.form["last_updated"]

        db.session.commit()

        return redirect(url_for("inventory"))

    return render_template(
        "edit_blood.html",
        blood=blood
    )


# =========================================================
# DELETE BLOOD STOCK
# =========================================================

@app.route("/delete_blood/<int:id>")
def delete_blood(id):

    if "user" not in session:

        return redirect(url_for("login"))

    blood = BloodInventory.query.get_or_404(id)

    db.session.delete(blood)

    db.session.commit()

    return redirect(url_for("inventory"))


# =========================================================
# BLOOD REQUEST
# =========================================================

@app.route("/request_blood", methods=["GET", "POST"])
def request_blood():

    if "user" not in session:

        return redirect(url_for("login"))

    if request.method == "POST":

        patient_name = request.form["patient_name"]

        blood_group = request.form["blood_group"]

        units = int(request.form["units"])

        hospital = request.form["hospital"]

        new_request = BloodRequest(
            patient_name=patient_name,
            blood_group=blood_group,
            units=units,
            hospital=hospital,
            status="Pending"
        )

        db.session.add(new_request)

        db.session.commit()

        return redirect(url_for("view_requests"))

    return render_template("request_blood.html")


# =========================================================
# VIEW BLOOD REQUESTS
# =========================================================

@app.route("/view_requests")
def view_requests():

    if "user" not in session:

        return redirect(url_for("login"))

    requests_data = BloodRequest.query.all()

    return render_template(
        "view_requests.html",
        requests_data=requests_data
    )


# =========================================================
# LOGOUT
# =========================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("home"))


# =========================================================
# CREATE DATABASE
# =========================================================

with app.app_context():

    db.create_all()


# =========================================================
# RUN APPLICATION
# =========================================================

if __name__ == "__main__":

    app.run(debug=os.getenv("FLASK_DEBUG", "false").lower() == "true")
