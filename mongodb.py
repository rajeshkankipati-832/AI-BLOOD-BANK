"""MongoDB connection factory; callers own and close the returned client."""
from pymongo import MongoClient


def create_mongo_client(uri, timeout_ms=2000):
    return MongoClient(uri, serverSelectionTimeoutMS=timeout_ms)


def get_database(client, database_name):
    return client[database_name]
