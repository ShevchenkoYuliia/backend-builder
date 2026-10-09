import sys
import os
from unittest.mock import AsyncMock, MagicMock

sys.path.insert(0, os.path.dirname(__file__))

mock_collection = MagicMock()
mock_collection.find = MagicMock(return_value=AsyncMock())
mock_collection.find_one = AsyncMock(return_value=None)
mock_collection.insert_one = AsyncMock()
mock_collection.update_one = AsyncMock()
mock_collection.delete_one = AsyncMock()

mock_db = MagicMock()
mock_db.__getitem__ = MagicMock(return_value=mock_collection)

mock_client = MagicMock()
mock_client.__getitem__ = MagicMock(return_value=mock_db)

motor_mock = MagicMock()
motor_mock.motor_asyncio.AsyncIOMotorClient = MagicMock(return_value=mock_client)
sys.modules["motor"] = motor_mock
sys.modules["motor.motor_asyncio"] = motor_mock.motor_asyncio
sys.modules["bson"] = MagicMock()
sys.modules["bson.ObjectId"] = MagicMock()
