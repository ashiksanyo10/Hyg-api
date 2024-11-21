from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import shutil
import os
import pandas as pd

app = FastAPI()

# CORS setup for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Update to specific domain in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "uploads/"
PROCESSED_DIR = "processed/"

# Ensure directories exist
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(PROCESSED_DIR, exist_ok=True)


@app.post("/process")
async def process_csv(file: UploadFile = File(...)):
    try:
        # Save the uploaded file temporarily
        temp_file_path = os.path.join(UPLOAD_DIR, file.filename)
        with open(temp_file_path, "wb") as temp_file:
            shutil.copyfileobj(file.file, temp_file)

        # Load and process the CSV
        df = pd.read_csv(temp_file_path)
        log_messages = []

        # 1. Check for duplicates in 'GTI' column
        duplicate_rows = df[df.duplicated(subset=['GTI'], keep=False)]
        if not duplicate_rows.empty:
            log_messages.append(f"Found {len(duplicate_rows)} duplicate entries in 'GTI' column.")
            df = df.drop_duplicates(subset=['GTI'], keep='first')

        # 2. Auto-fill 'Age rating ID' based on 'Content Descriptors'
        def auto_fill_age_rating(content_desc):
            if isinstance(content_desc, str):
                if content_desc.startswith(("General", "Very mild")):
                    return 2
                elif content_desc.startswith("Mild"):
                    return 9
                elif content_desc.startswith("Strong"):
                    return 156
                elif content_desc.startswith("High impact"):
                    return 154
            return 147  # Default value

        df['Age rating ID'] = df['Age rating ID'].fillna(df['Content Descriptors'].apply(auto_fill_age_rating))
        log_messages.append("Filled missing 'Age rating ID' values based on 'Content Descriptors'.")

        # 3. Remove invalid characters from 'Other title names'
        def remove_invalid_characters(title):
            if isinstance(title, str):
                return ''.join([ch for ch in title if ch.isascii()])
            return title

        df['Other title names'] = df['Other title names'].apply(remove_invalid_characters)
        log_messages.append("Removed invalid characters from 'Other title names'.")

        # Save the processed file
        processed_file_path = os.path.join(PROCESSED_DIR, f"Processed_{file.filename}")
        df.to_csv(processed_file_path, index=False)

        log_messages.append(f"File processed successfully. Saved as {processed_file_path}.")
        return JSONResponse(content={
            "message": "Processing complete.",
            "logs": log_messages,
            "download_url": f"/download/{os.path.basename(processed_file_path)}"
        })

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")


@app.get("/download/{file_name}")
def download_file(file_name: str):
    file_path = os.path.join(PROCESSED_DIR, file_name)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found.")
    return FileResponse(file_path, filename=file_name)
