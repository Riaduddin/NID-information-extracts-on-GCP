from motor.motor_asyncio import AsyncIOMotorClient
from src.utils import  MONGO_URI
from dotenv import load_dotenv
from fastapi_mail import FastMail, MessageSchema
import os
from src.utils.config import conf

# Initialize FastAPI-Mail
mail = FastMail(conf)

# Load environment variables
load_dotenv()
# MongoDB connection
client = AsyncIOMotorClient(MONGO_URI)
db = client['NID_information']  # Replace with your database name
collection = db['extracted_text']
# Function to generate a sequential row number
async def get_next_row_number():
    # Get the highest current row number from MongoDB
    last_document = await collection.find_one(sort=[("_id", -1)])
    if last_document:
        return last_document["_id"] + 1  # Increment the highest row number
    return 1  # Start at 1 if the collection is empty

async def insert_document(document):
    await collection.insert_one(document)

async def send_email(missing_fields,row_number):
    email_body = f"The following fields are missing: {', '.join(missing_fields.keys())} for row {row_number}."
    message = MessageSchema(
        subject="Missing Data Alert",
        recipients=[os.getenv("NOTIFICATION_EMAIL")],  # Set the recipient email in .env
        body=email_body,
        subtype="plain"
    )
    await mail.send_message(message)
    