from motor.motor_asyncio import AsyncIOMotorClient
import asyncio
import os
from dotenv import load_dotenv

load_dotenv() #used to load all the env variables from .env file

Mongo_URL = os.getenv("MONGO_URL")
client = AsyncIOMotorClient(Mongo_URL)
database = client.sql_assistant
user_collection = database.get_collection("user_master")
query_collection = database.get_collection("query_master")



