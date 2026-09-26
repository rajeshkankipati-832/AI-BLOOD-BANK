from pymongo import MongoClient

# Connect to MongoDB
client = MongoClient("mongodb://localhost:27017/")

# Select database
db = client["AI_Blood_Bank"]

# Select users collection
users = db["users"]

# Admin details
admin_email = "admin@aibloodbank.com"
admin_password = "admin123"

# Check whether admin already exists
existing_admin = users.find_one({"email": admin_email})

if existing_admin:
    print("Admin account already exists.")
else:
    admin = {
        "fullname": "AI Blood Bank Admin",
        "email": admin_email,
        "phone": "9999999999",
        "blood_group": "",
        "age": 25,
        "gender": "",
        "password": admin_password,
        "donor": False,
        "role": "admin"
    }

    users.insert_one(admin)

    print("==============================")
    print("ADMIN ACCOUNT CREATED")
    print("==============================")
    print("Email:    admin@aibloodbank.com")
    print("Password: admin123")
    print("Role:     admin")
    print("==============================")

client.close()