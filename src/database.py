from motor.motor_asyncio import AsyncIOMotorClient
from src.utils import  MONGO_URI
from models import Item
from bson import ObjectId
from typing import List

class Database:
    def __init__(self, mongo_uri: str):
        self.client = AsyncIOMotorClient(mongo_uri)
        self.db = self.client['NID_information']  # Replace with your database name
        self.collection = self.db['extracted_text']

    async def fetch_all(self) -> List[Item]:
        items = []
        async for item in self.collection.find():
            item['id'] = str(item['_id'])
            items.append(item)
        return items

    async def fetch_one(self, id: str) -> Item:
        item = await self.collection.find_one({"_id": ObjectId(id)})
        if item:
            item['id'] = str(item['_id'])
            return item
        return None

    async def create(self, item: Item) -> str:
        result = await self.collection.insert_one(item.dict(exclude={"id"}))
        return str(result.inserted_id)

    async def update(self, id: str, item: Item):
        await self.collection.update_one({"_id": ObjectId(id)}, {"$set": item.dict(exclude={"id"})})

    async def delete(self, id: str):
        await self.collection.delete_one({"_id": ObjectId(id)})
