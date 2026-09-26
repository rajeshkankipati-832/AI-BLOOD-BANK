"""Environment driven application configuration."""
import os
from pathlib import Path
import secrets
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


class Config:
    # Random local fallback keeps development usable; set a stable secret in deployment.
    SECRET_KEY = os.getenv("SECRET_KEY") or secrets.token_hex(32)
    MONGO_URI = os.getenv("MONGO_URI", "mongodb://127.0.0.1:27017")
    MONGO_DB = os.getenv("MONGO_DB", "AI_Blood_Bank")
    BLOOD_GROUPS = ("A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-")
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    @classmethod
    def validate(cls):
        if not cls.SECRET_KEY:
            raise RuntimeError("Set SECRET_KEY in the environment before starting the application.")
