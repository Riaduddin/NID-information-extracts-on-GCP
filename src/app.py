import base64
from fastapi import FastAPI, File, UploadFile
import vertexai
from vertexai.generative_models import GenerativeModel, Part, SafetySetting
import json
import os
import re
from motor.motor_asyncio import AsyncIOMotorClient
from google.cloud import storage
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = FastAPI()

# MongoDB connection
MONGO_URI = os.getenv("MONGO_URI")
client = AsyncIOMotorClient(MONGO_URI)
db = client['NID_information']  # Replace with your database name
collection = db['extracted_text']

# Google Cloud Storage configuration
GCS_BUCKET_NAME = "mongo_nid"
gcs_client = storage.Client()
bucket = gcs_client.bucket(GCS_BUCKET_NAME)

# Notification email is fetched from environment variables (hidden from the user)
NOTIFICATION_EMAIL = os.getenv("NOTIFICATION_EMAIL")
# Initialize FastAPI-Mail
conf = ConnectionConfig(
    MAIL_USERNAME=os.getenv("EMAIL_USERNAME"),
    MAIL_PASSWORD=os.getenv("EMAIL_PASSWORD"),
    MAIL_FROM=os.getenv("EMAIL_USERNAME"),
    MAIL_PORT=587,
    MAIL_SERVER="smtp.gmail.com",
    MAIL_STARTTLS=True,               #MAIL_TLS=True,
    MAIL_SSL_TLS=False,              #      MAIL_SSL=False,
    USE_CREDENTIALS=True
)

mail = FastMail(conf)
# Initialize GCP Vertex AI
PROJECT_ID = "edge-trainee"
LOCATION = "us-central1"

# Initialization happens only once at startup
vertexai.init(project=PROJECT_ID, location=LOCATION)

# Function to generate a sequential row number
async def get_next_row_number():
    # Get the highest current row number from MongoDB
    last_document = await collection.find_one(sort=[("_id", -1)])
    if last_document:
        return last_document["_id"] + 1  # Increment the highest row number
    return 1  # Start at 1 if the collection is empty

@app.post("/generate")
async def generate(image: UploadFile = File(...)):
    try:
        # Read the image file and convert it to base64
        image_data = await image.read()
        image_b64 = base64.b64encode(image_data).decode('utf-8')
        # Generate a sequential row number
        row_number = await get_next_row_number()  
        
        # Create a simple image name using the row number
        image_name = f"{row_number}"

        # Upload image to GCS with the unique name
        blob = bucket.blob(image_name)
        blob.upload_from_string(image_data, content_type=image.content_type)
        #https://storage.cloud.google.com/mongo_nid/3
        # Generate the image URL
        image_url = f"https://storage.cloud.google.com/{GCS_BUCKET_NAME}/{image_name}"
        # Create Part for image using base64 decoded data
        image_part = Part.from_data(
            mime_type=image.content_type,
            data=base64.b64decode(image_b64)
        )

        # Create the text part with instructions
        text_part = "extract text from the image and translate in English. And keep them in dictionary format \
        because I want to store it my csv file and where key value should included name, father name, mother name, \
            Birth, ID NO, Address and Blood Group. If any key value misses should be given as Not Provided."

        # Define generation config
        generation_config = {
            "max_output_tokens": 8192,
            "temperature": 0.1,
            "top_p": 0.95,
        }

        # Define safety settings
        safety_settings = [
            SafetySetting(
                category=SafetySetting.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                threshold=SafetySetting.HarmBlockThreshold.OFF
            ),
            SafetySetting(
                category=SafetySetting.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                threshold=SafetySetting.HarmBlockThreshold.OFF
            ),
            SafetySetting(
                category=SafetySetting.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                threshold=SafetySetting.HarmBlockThreshold.OFF
            ),
            SafetySetting(
                category=SafetySetting.HarmCategory.HARM_CATEGORY_HARASSMENT,
                threshold=SafetySetting.HarmBlockThreshold.OFF
            ),
        ]

        # Initialize the model
        model = GenerativeModel("gemini-1.5-flash-002")

        # Call Vertex AI's content generation API
        response = model.generate_content(
            [image_part, text_part],
            generation_config=generation_config,
            safety_settings=safety_settings,
            stream=False,
        )


        # Access the response text directly (not iterable)
        result_text = response.text
        cleaned_text = re.search(r'\{[\s\S]+\}', result_text).group()
        
        data_dict = json.loads(cleaned_text)

        # Store extracted data in MongoDB with the row_number as the document ID
        document = {
            "_id": row_number,  # Use the row number as the MongoDB document ID
            "extracted_data": data_dict,
            "image_url": image_url,
            "status": "pending" if "Not Provided" in data_dict.values() else "completed"
        }
        await collection.insert_one(document)
        # Check for missing values in the data
        missing_fields = {key: value for key, value in data_dict.items() if value == "Not Provided"}
        # If missing fields exist, send an email
        if missing_fields:
            email_body = f"The following fields are missing: {', '.join(missing_fields.keys())} for row {row_number}."
            message = MessageSchema(
                subject="Missing Data Alert",
                recipients=[os.getenv("NOTIFICATION_EMAIL")],  # Set the recipient email in .env
                body=email_body,
                subtype="plain"
            )
            await mail.send_message(message)

        return {"message": "Data extracted successfully", "document_id": row_number, "data": data_dict}

        # return {"result": data_dict}

    except Exception as e:
        return {"error": str(e)}
