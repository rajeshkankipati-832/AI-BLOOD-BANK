from pymongo import MongoClient

try:
    client = MongoClient(
        "mongodb://localhost:27017/",
        serverSelectionTimeoutMS=5000
    )

    client.admin.command("ping")

    print("================================")
    print("MongoDB connection successful!")
    print("MongoDB Server: localhost")
    print("Port: 27017")
    print("================================")

    db = client["AI_Blood_Bank"]

    print("Database selected:", db.name)

    client.close()

except Exception as e:
    print("MongoDB connection failed!")
    print("Error:", e)