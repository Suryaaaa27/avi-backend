# backend/database/db_connection.py
"""
=====================================================
📦 db_connection.py
-----------------------------------------------------
Handles MongoDB database connection using PyMongo.
Environment variables are used for secure credentials.
=====================================================
"""

import os
from pymongo import MongoClient
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ==============================
# 🗄️ Database Configuration
# ==============================
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGO_DB", "avi_system")

# ==============================
# ⚙️ MongoDB Connection Setup
# ==============================
try:
    client = MongoClient(MONGO_URI)
    db = client[MONGO_DB]
    print(f"✅ Connected to MongoDB database: {MONGO_DB}")
except Exception as e:
    print(f"⚠️ MongoDB connection failed: {e}")
    db = None


# Utility function for modules
def get_collection(name: str):
    """
    Get a MongoDB collection safely.

    Args:
        name (str): Collection name
    Returns:
        pymongo.collection.Collection
    """
    if db is not None:
      return db[name]
    else:
     raise ConnectionError("Database not connected. Check MongoDB configuration.")

