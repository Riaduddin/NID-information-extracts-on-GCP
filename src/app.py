import base64
from fastapi import FastAPI, File, UploadFile
import vertexai
from vertexai.generative_models import GenerativeModel, Part, SafetySetting
import json
import csv
import os
import re

app = FastAPI()

# Initialize GCP Vertex AI
PROJECT_ID = "edge-trainee"
LOCATION = "us-central1"

# Initialization happens only once at startup
vertexai.init(project=PROJECT_ID, location=LOCATION)

@app.post("/generate")
async def generate(image: UploadFile = File(...)):
    try:
        # Read the image file and convert it to base64
        image_data = await image.read()
        image_b64 = base64.b64encode(image_data).decode('utf-8')

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

        # CSV file path
        csv_file = "vertex_ai_responses.csv"

        # Check if file exists; if not, create a new file with headers
        # file_exists = os.path.isfile(csv_file)

        # Save response as CSV
        with open(csv_file, mode="a", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=data_dict.keys())
            # Write the header if the file doesn't exist
            # if not file_exists:
            if file.tell()==0:
                writer.writeheader()
            # Write the row of extracted data
            writer.writerow(data_dict)

        return {"result": data_dict}

    except Exception as e:
        return {"error": str(e)}
