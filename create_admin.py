"""Create an initial administrator using credentials supplied at runtime."""
import getpass
import os

from pymongo import MongoClient
from werkzeug.security import generate_password_hash


def main():
    email = os.getenv("ADMIN_EMAIL", "").strip().lower()
    if not email:
        email = input("Admin email: ").strip().lower()
    password = os.getenv("ADMIN_PASSWORD") or getpass.getpass("Admin password (8+ characters): ")
    if "@" not in email or len(password) < 8:
        raise SystemExit("Provide a valid email and a password of at least 8 characters.")
    uri = os.getenv("MONGO_URI", "mongodb://127.0.0.1:27017")
    database = os.getenv("MONGO_DB", "AI_Blood_Bank")
    with MongoClient(uri, serverSelectionTimeoutMS=5000) as client:
        users = client[database]["users"]
        if users.find_one({"email": email}):
            raise SystemExit("An account with that email already exists; no changes made.")
        users.insert_one({"fullname": "AI Blood Bank Admin", "email": email,
            "phone": "", "blood_group": "", "age": None, "gender": "",
            "password": generate_password_hash(password), "donor": False, "role": "admin"})
    print(f"Administrator account created for {email}.")


if __name__ == "__main__":
    main()
