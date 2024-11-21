from flask import Flask, request, jsonify, send_from_directory
import os
import shutil
import pandas as pd

app = Flask(__name__)

UPLOAD_DIR = "uploads/"
PROCESSED_DIR = "processed/"

# Ensure directories exist
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(PROCESSED_DIR, exist_ok=True)

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    # Save the uploaded file temporarily
    temp_file_path = os.path.join(UPLOAD_DIR, file.filename)
    file.save(temp_file_path)

    # Process the file
    try:
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
        return jsonify({
            "message": "Processing complete.",
            "logs": log_messages,
            "download_url": f"/download/{os.path.basename(processed_file_path)}"
        })

    except Exception as e:
        return jsonify({"error": f"Error processing file: {str(e)}"}), 500


@app.route('/download/<filename>', methods=['GET'])
def download_file(filename):
    file_path = os.path.join(PROCESSED_DIR, filename)
    if not os.path.exists(file_path):
        return jsonify({"error": "File not found"}), 404
    return send_from_directory(PROCESSED_DIR, filename)


if __name__ == '__main__':
    app.run(debug=True)
