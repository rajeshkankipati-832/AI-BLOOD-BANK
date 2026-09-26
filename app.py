from flask import Flask, render_template, request, redirect, url_for, session
from pymongo import MongoClient
from bson.objectid import ObjectId
from datetime import datetime
from functools import wraps


app = Flask(__name__)

# =========================================================
# CONFIGURATION
# =========================================================

app.secret_key = "AIBloodBank2026"

MONGO_URI = "mongodb://localhost:27017/"

client = MongoClient(MONGO_URI)

db = client["AI_Blood_Bank"]


# =========================================================
# COLLECTIONS
# =========================================================

users_collection = db["users"]

blood_inventory_collection = db["blood_inventory"]

# IMPORTANT:
# MongoDB collection is named "requests"
blood_requests_collection = db["requests"]

hospitals_collection = db["hospitals"]

predictions_collection = db["predictions"]


# =========================================================
# DATABASE CONNECTION TEST
# =========================================================

try:

    client.admin.command("ping")

    print("========================================")
    print("MongoDB connected successfully!")
    print("Database: AI_Blood_Bank")
    print("========================================")

except Exception as e:

    print("MongoDB connection error:", e)


# =========================================================
# ADMIN CHECK
# =========================================================

def admin_required(function):

    @wraps(function)
    def wrapper(*args, **kwargs):

        if "user" not in session:

            return redirect(url_for("login"))

        if session.get("role") != "admin":

            return """
            <div style="
                text-align:center;
                margin-top:100px;
                font-family:Arial;
            ">

                <h2 style="color:red;">
                    Access Denied
                </h2>

                <p>
                    Only administrators can access this page.
                </p>

                <a href="/dashboard">
                    Back to Dashboard
                </a>

            </div>
            """

        return function(*args, **kwargs)

    return wrapper


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

        fullname = request.form.get(
            "fullname",
            ""
        ).strip()

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        phone = request.form.get(
            "phone",
            ""
        ).strip()

        blood_group = request.form.get(
            "blood_group",
            ""
        ).strip()

        age = request.form.get(
            "age",
            ""
        ).strip()

        gender = request.form.get(
            "gender",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )

        donor = True if request.form.get("donor") else False


        # Check existing user

        existing_user = users_collection.find_one({

            "email": email

        })

        if existing_user:

            return "Email already registered."


        # Convert age

        try:

            age_value = int(age) if age else None

        except ValueError:

            age_value = None


        # Create user

        user_data = {

            "fullname": fullname,

            "email": email,

            "phone": phone,

            "blood_group": blood_group,

            "age": age_value,

            "gender": gender,

            "password": password,

            "donor": donor,

            "role": "user",

            "created_at": datetime.now()

        }


        users_collection.insert_one(user_data)


        return redirect(
            url_for("login")
        )


    return render_template(
        "signup.html"
    )


# =========================================================
# LOGIN
# =========================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        password = request.form.get(
            "password",
            ""
        )


        user = users_collection.find_one({

            "email": email,

            "password": password

        })


        if user:

            session["user"] = user.get(
                "fullname",
                "User"
            )

            session["user_id"] = str(
                user["_id"]
            )

            session["role"] = user.get(
                "role",
                "user"
            )


            return redirect(
                url_for("dashboard")
            )


        return "Invalid Email or Password"


    return render_template(
        "login.html"
    )


# =========================================================
# DASHBOARD
# =========================================================

@app.route("/dashboard")
def dashboard():

    if "user" not in session:

        return redirect(
            url_for("login")
        )


    # =====================================================
    # DONOR COUNT
    # =====================================================

    donor_count = users_collection.count_documents({

        "donor": True

    })


    # =====================================================
    # TOTAL BLOOD UNITS
    # =====================================================

    total_blood_units = 0


    inventory_data = list(

        blood_inventory_collection.find({})

    )


    for blood in inventory_data:

        try:

            total_blood_units += int(

                blood.get(
                    "units",
                    0
                )

            )

        except (ValueError, TypeError):

            pass


    # =====================================================
    # HOSPITAL COUNT
    # =====================================================

    hospital_count = hospitals_collection.count_documents({})


    # =====================================================
    # BLOOD REQUEST COUNT
    # =====================================================

    request_count = blood_requests_collection.count_documents({})


    # =====================================================
    # DEMAND PREDICTION
    # =====================================================

    if request_count >= 20:

        demand_prediction = "High"

    elif request_count >= 10:

        demand_prediction = "Medium"

    else:

        demand_prediction = "Low"


    return render_template(

        "dashboard.html",

        username=session["user"],

        role=session.get(
            "role",
            "user"
        ),

        donor_count=donor_count,

        total_blood_units=total_blood_units,

        hospital_count=hospital_count,

        request_count=request_count,

        demand_prediction=demand_prediction

    )


# =========================================================
# VIEW BLOOD INVENTORY
# NORMAL USERS + ADMIN
# =========================================================

@app.route("/inventory")
def inventory():

    if "user" not in session:

        return redirect(
            url_for("login")
        )


    blood_data = list(

        blood_inventory_collection.find({})

    )


    return render_template(

        "inventory.html",

        blood_data=blood_data,

        role=session.get(
            "role",
            "user"
        )

    )


# =========================================================
# ADD BLOOD STOCK
# ADMIN ONLY
# =========================================================

@app.route(
    "/add_blood",
    methods=["GET", "POST"]
)
@admin_required
def add_blood():

    if request.method == "POST":

        blood_group = request.form.get(
            "blood_group",
            ""
        ).strip()

        units = request.form.get(
            "units",
            "0"
        ).strip()

        last_updated = request.form.get(
            "last_updated",
            ""
        ).strip()


        try:

            units_value = int(units)

        except ValueError:

            units_value = 0


        blood_data = {

            "blood_group": blood_group,

            "units": units_value,

            "last_updated": last_updated,

            "created_at": datetime.now()

        }


        blood_inventory_collection.insert_one(
            blood_data
        )


        return redirect(
            url_for("inventory")
        )


    return render_template(
        "add_blood.html"
    )


# =========================================================
# EDIT BLOOD STOCK
# ADMIN ONLY
# =========================================================

@app.route(
    "/edit_blood/<id>",
    methods=["GET", "POST"]
)
@admin_required
def edit_blood(id):

    try:

        blood = blood_inventory_collection.find_one({

            "_id": ObjectId(id)

        })

    except Exception:

        return "Invalid blood record ID."


    if not blood:

        return "Blood record not found."


    if request.method == "POST":

        blood_group = request.form.get(
            "blood_group",
            ""
        ).strip()

        units = request.form.get(
            "units",
            "0"
        ).strip()

        last_updated = request.form.get(
            "last_updated",
            ""
        ).strip()


        try:

            units_value = int(units)

        except ValueError:

            units_value = 0


        blood_inventory_collection.update_one(

            {
                "_id": ObjectId(id)
            },

            {
                "$set": {

                    "blood_group": blood_group,

                    "units": units_value,

                    "last_updated": last_updated,

                    "updated_at": datetime.now()

                }

            }

        )


        return redirect(
            url_for("inventory")
        )


    return render_template(

        "edit_blood.html",

        blood=blood

    )


# =========================================================
# DELETE BLOOD STOCK
# ADMIN ONLY
# =========================================================

@app.route("/delete_blood/<id>")
@admin_required
def delete_blood(id):

    try:

        blood_inventory_collection.delete_one({

            "_id": ObjectId(id)

        })

    except Exception:

        return "Invalid blood record ID."


    return redirect(
        url_for("inventory")
    )


# =========================================================
# DONATE BLOOD
# NORMAL USER + ADMIN
# =========================================================

@app.route(
    "/donate_blood",
    methods=["GET", "POST"]
)
def donate_blood():

    if "user" not in session:

        return redirect(
            url_for("login")
        )


    if request.method == "POST":

        fullname = request.form.get(
            "fullname",
            session.get("user", "")
        ).strip()

        phone = request.form.get(
            "phone",
            ""
        ).strip()

        blood_group = request.form.get(
            "blood_group",
            ""
        ).strip()

        age = request.form.get(
            "age",
            ""
        ).strip()

        gender = request.form.get(
            "gender",
            ""
        ).strip()


        try:

            age_value = int(age) if age else None

        except ValueError:

            age_value = None


        # Update existing user as donor

        try:

            user_id = ObjectId(
                session["user_id"]
            )

            users_collection.update_one(

                {
                    "_id": user_id
                },

                {
                    "$set": {

                        "fullname": fullname,

                        "phone": phone,

                        "blood_group": blood_group,

                        "age": age_value,

                        "gender": gender,

                        "donor": True,

                        "donor_registered_at":
                            datetime.now()

                    }

                }

            )

        except Exception:

            return "Unable to update donor information."


        return redirect(
            url_for("dashboard")
        )


    # Get current user information

    try:

        current_user = users_collection.find_one({

            "_id": ObjectId(
                session["user_id"]
            )

        })

    except Exception:

        current_user = None


    return render_template(

        "donate_blood.html",

        user=current_user

    )


# =========================================================
# BLOOD REQUEST
# NORMAL USERS + ADMIN
# =========================================================

@app.route(
    "/request_blood",
    methods=["GET", "POST"]
)
def request_blood():

    if "user" not in session:

        return redirect(
            url_for("login")
        )


    if request.method == "POST":

        patient_name = request.form.get(
            "patient_name",
            ""
        ).strip()

        blood_group = request.form.get(
            "blood_group",
            ""
        ).strip()

        units = request.form.get(
            "units",
            "0"
        ).strip()

        hospital = request.form.get(
            "hospital",
            ""
        ).strip()


        try:

            units_value = int(units)

        except ValueError:

            units_value = 0


        new_request = {

            "patient_name": patient_name,

            "blood_group": blood_group,

            "units": units_value,

            "hospital": hospital,

            "status": "Pending",

            "requested_by":
                session.get("user"),

            "requested_by_id":
                session.get("user_id"),

            "created_at":
                datetime.now()

        }


        blood_requests_collection.insert_one(
            new_request
        )


        return redirect(
            url_for("view_requests")
        )


    return render_template(
        "request_blood.html"
    )


# =========================================================
# VIEW BLOOD REQUESTS
# ADMIN = ALL REQUESTS
# USER = OWN REQUESTS
# =========================================================

@app.route("/view_requests")
def view_requests():

    if "user" not in session:

        return redirect(
            url_for("login")
        )


    if session.get("role") == "admin":

        requests_data = list(

            blood_requests_collection.find({})

        )

    else:

        requests_data = list(

            blood_requests_collection.find({

                "requested_by_id":
                    session.get("user_id")

            })

        )


    return render_template(

        "view_requests.html",

        requests_data=requests_data,

        role=session.get(
            "role",
            "user"
        )

    )


# =========================================================
# APPROVE BLOOD REQUEST
# ADMIN ONLY
# =========================================================

@app.route("/approve_request/<id>")
@admin_required
def approve_request(id):

    try:

        blood_requests_collection.update_one(

            {
                "_id": ObjectId(id)
            },

            {
                "$set": {

                    "status": "Approved",

                    "approved_at":
                        datetime.now()

                }

            }

        )

    except Exception:

        return "Invalid request ID."


    return redirect(
        url_for("view_requests")
    )


# =========================================================
# REJECT BLOOD REQUEST
# ADMIN ONLY
# =========================================================

@app.route("/reject_request/<id>")
@admin_required
def reject_request(id):

    try:

        blood_requests_collection.update_one(

            {
                "_id": ObjectId(id)
            },

            {
                "$set": {

                    "status": "Rejected",

                    "rejected_at":
                        datetime.now()

                }

            }

        )

    except Exception:

        return "Invalid request ID."


    return redirect(
        url_for("view_requests")
    )


# =========================================================
# HOSPITALS
# ADMIN ONLY
# =========================================================

@app.route("/hospitals")
@admin_required
def hospitals():

    hospitals_data = list(

        hospitals_collection.find({})

    )


    return render_template(

        "hospitals.html",

        hospitals_data=hospitals_data

    )


# =========================================================
# ADD HOSPITAL
# ADMIN ONLY
# =========================================================

@app.route(
    "/add_hospital",
    methods=["GET", "POST"]
)
@admin_required
def add_hospital():

    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()

        location = request.form.get(
            "location",
            ""
        ).strip()

        phone = request.form.get(
            "phone",
            ""
        ).strip()


        hospital_data = {

            "name": name,

            "location": location,

            "phone": phone,

            "connected": True,

            "created_at": datetime.now()

        }


        hospitals_collection.insert_one(
            hospital_data
        )


        return redirect(
            url_for("hospitals")
        )


    return render_template(
        "add_hospital.html"
    )


# =========================================================
# DELETE HOSPITAL
# ADMIN ONLY
# =========================================================

@app.route("/delete_hospital/<id>")
@admin_required
def delete_hospital(id):

    try:

        hospitals_collection.delete_one({

            "_id": ObjectId(id)

        })

    except Exception:

        return "Invalid hospital ID."


    return redirect(
        url_for("hospitals")
    )


# =========================================================
# AI PREDICTION
# TEMPORARY RULE-BASED VERSION
# =========================================================

@app.route("/ai_prediction")
def ai_prediction():

    if "user" not in session:

        return redirect(
            url_for("login")
        )


    request_count = blood_requests_collection.count_documents({})


    if request_count >= 20:

        prediction = "High"

    elif request_count >= 10:

        prediction = "Medium"

    else:

        prediction = "Low"


    return render_template(

        "ai_prediction.html",

        prediction=prediction,

        request_count=request_count

    )


# =========================================================
# LOGOUT
# =========================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(
        url_for("home")
    )


# =========================================================
# RUN APPLICATION
# =========================================================

if __name__ == "__main__":

    app.run(
        debug=True
    )