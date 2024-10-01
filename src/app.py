import base64
from fastapi import FastAPI, File, UploadFile
import vertexai
from vertexai.generative_models import GenerativeModel, Part, SafetySetting
import json
import os
import re
from google.cloud import storage
from dotenv import load_dotenv
# from src.utils.config import conf
from src.utils import PROJECT_ID, LOCATION, GCS_BUCKET_NAME, SAFETYSETTING
from src.utils.connections import get_next_row_number,insert_document,send_email

# Load environment variables
load_dotenv()

app = FastAPI()

# Google Cloud Storage configuration
gcs_client = storage.Client()
bucket = gcs_client.bucket(GCS_BUCKET_NAME)

# Initialization happens only once at startup
vertexai.init(project=PROJECT_ID, location=LOCATION)


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


        # Initialize the model
        model = GenerativeModel("gemini-1.5-flash-002")

        # Call Vertex AI's content generation API
        response = model.generate_content(
            [image_part, text_part],
            generation_config=generation_config,
            safety_settings=SAFETYSETTING,
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
        await insert_document(document)
        # Check for missing values in the data
        missing_fields = {key: value for key, value in data_dict.items() if value == "Not Provided"}
        # If missing fields exist, send an email
        if missing_fields:
            await send_email(missing_fields,row_number)

        return {"message": "Data extracted successfully", "document_id": row_number, "data": data_dict}

        # return {"result": data_dict}

    except Exception as e:
        return {"error": str(e)}
