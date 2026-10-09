import os

from motor.motor_asyncio import AsyncIOMotorClient


MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.getenv("MONGO_DB_NAME", "backend_builder")

client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]

users_collection = db["users"]
projects_collection = db["projects"]
chat_history_collection = db["chat_history"]
