"""Authentication and legacy password migration helpers."""
from werkzeug.security import check_password_hash, generate_password_hash


def hash_password(password):
    return generate_password_hash(password)


def verify_and_upgrade_password(users, user, password):
    stored = (user or {}).get("password", "")
    if not stored:
        return False
    try:
        if check_password_hash(stored, password):
            return True
    except (ValueError, TypeError):
        pass
    if stored == password:
        users.update_one({"_id": user["_id"]}, {"$set": {"password": hash_password(password)}})
        return True
    return False
