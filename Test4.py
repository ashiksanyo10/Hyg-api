from flask import Flask, request, jsonify
import os
import re
import polars as pl
from werkzeug.utils import secure_filename
import logging
from datetime import datetime

app = Flask(__name__)

# Configuration
UPLOAD_FOLDER = 'uploads/'
ALLOWED_EXTENSIONS = {'csv'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB file limit

# Ensure upload folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Helper functions
def allowed_file(filename):
    """Check if the file has a valid extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def clean_invalid_chars(text):
    """Remove non-Latin characters."""
    return re.sub(r'[^\x00-\x7F]+', '', text)

def validate_csv_data(df):
    """Validate CSV data based on custom rules."""
    logs = []

    for row_index, row in df.iter_rows(named=True):
        row_log = {}

        # Example 1: Blank values in required fields
        required_columns = ['Title', 'Release Year', 'Age rating']
        for col in required_columns:
            if col in row and (row[col] is None or row[col] == ''):
                logs.append({
                    "line": row_index + 1,
                    "column": col,
                    "message": f"Missing value in required column: {col}"
                })

        # Example 2: Age rating validation
        if "Age rating" in row and isinstance(row["Age rating"], str):
            age_rating = row["Age rating"]
            valid_ratings = ['G', 'PG', 'M', 'R']
            if age_rating not in valid_ratings:
                logs.append({
                    "line": row_index + 1,
                    "column": "Age rating",
                    "message": f"Invalid age rating: {age_rating}"
                })
        
        # Example 3: Textual Cleaning (Removing Invalid Characters)
        if "Other title names" in row and isinstance(row["Other title names"], str):
            original_title = row["Other title names"]
            cleaned_title = clean_invalid_chars(original_title)
            if cleaned_title != original_title:
                logs.append({
                    "line": row_index + 1,
                    "column": "Other title names",
                    "message": f"Cleaned title: {original_title} -> {cleaned_title}"
                })

    return logs

@app.route('/upload', methods=['POST'])
def upload_file():
    """API endpoint for CSV upload and validation."""
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)

        logger.info(f"File {filename} uploaded successfully.")

        # Process the file
        try:
            df = pl.read_csv(file_path)
            logs = validate_csv_data(df)
            # Return logs as response
            return jsonify(logs)
        
        except Exception as e:
            logger.error(f"Error processing the file: {str(e)}")
            return jsonify({"error": "Error processing the CSV file"}), 500

    return jsonify({"error": "Invalid file format, only CSV files are allowed."}), 400

@app.route('/download/<filename>', methods=['GET'])
def download_file(filename):
    """Provide the option to download the cleaned CSV."""
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if os.path.exists(file_path):
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)
    return jsonify({"error": "File not found"}), 404

@app.errorhandler(404)
def not_found_error(error):
    """Handle 404 errors."""
    return jsonify({"error": "Not Found"}), 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    return jsonify({"error": "Internal Server Error"}), 500

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000)
