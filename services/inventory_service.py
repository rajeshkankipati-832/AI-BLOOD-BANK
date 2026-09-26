"""Inventory and request-decision business logic."""
from datetime import datetime, timezone

from pymongo import ReturnDocument


def approve_request(inventory, requests_collection, record):
    units = int(record.get("units", 0))
    stock = inventory.find_one_and_update(
        {"blood_group": record.get("blood_group"), "units": {"$gte": units}},
        {"$inc": {"units": -units}, "$set": {"updated_at": datetime.now(timezone.utc)}},
        return_document=ReturnDocument.AFTER,
    )
    if not stock:
        return "insufficient_stock"
    updated = requests_collection.update_one(
        {"_id": record["_id"], "status": "Pending"},
        {"$set": {"status": "Approved", "reviewed_at": datetime.now(timezone.utc)}},
    )
    if not updated.modified_count:
        inventory.update_one({"_id": stock["_id"]}, {"$inc": {"units": units}})
        return "already_reviewed"
    return "approved"


def reject_request(requests_collection, record):
    return requests_collection.update_one(
        {"_id": record["_id"], "status": "Pending"},
        {"$set": {"status": "Rejected", "reviewed_at": datetime.now(timezone.utc)}},
    ).modified_count == 1
