"""Create non-destructive query indexes for the existing collections."""
from pymongo import ASCENDING, DESCENDING, MongoClient

from config import Config


def ensure_indexes(database):
    """Create non-unique indexes only; no existing rows are removed or rewritten."""
    return {
        "users_email": database.users.create_index([("email", ASCENDING)], name="users_email_idx"),
        "requests_owner_created": database.requests.create_index(
            [("requested_by_id", ASCENDING), ("created_at", DESCENDING)], name="requests_owner_created_idx"),
        "requests_status_created": database.requests.create_index(
            [("status", ASCENDING), ("created_at", DESCENDING)], name="requests_status_created_idx"),
        "inventory_group": database.blood_inventory.create_index(
            [("blood_group", ASCENDING)], name="inventory_group_idx"),
        "hospitals_name": database.hospitals.create_index([("name", ASCENDING)], name="hospitals_name_idx"),
        "predictions_owner_created": database.predictions.create_index(
            [("requested_by_id", ASCENDING), ("created_at", DESCENDING)], name="predictions_owner_created_idx"),
    }


if __name__ == "__main__":
    with MongoClient(Config.MONGO_URI, serverSelectionTimeoutMS=5000) as mongo:
        mongo.admin.command("ping")
        print(ensure_indexes(mongo[Config.MONGO_DB]))
