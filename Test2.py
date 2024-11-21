from flask import Flask, render_template, request, jsonify
import polars as pl
import re
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)

# Configuration for file uploads
app.config['UPLOAD_FOLDER'] = 'uploads/'
app.config['ALLOWED_EXTENSIONS'] = {'csv'}
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # Max file size 16 MB

# Sample content descriptors for age rating and their corresponding IDs
content_descriptors = {
    "General": {"age_rating_id": 2},
    "Very mild": {"age_rating_id": 2},
    "Mild": {"age_rating_id": 9},
    "Strong": {"age_rating_id": 156},
    "High impact": {"age_rating_id": 154}
}

# Default age rating ID if no prefix is found
default_age_rating_id = 147


# Helper function to check if the file is allowed
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


# Function to process the CSV file and return logs
def process_file(file_path):
    logs = []
    try:
        # Read the CSV file with Polars
        df = pl.read_csv(file_path)

        # Process the data
        for row_index, row in df.iter_rows(named=True):
            row_log = {}

            # Check for blanks and log
            for col_name, value in row.items():
                if value == '' or value is None:
                    logs.append({
                        "line": row_index + 1,
                        "column": col_name,
                        "message": "Blank value found"
                    })

            # Age rating logic
            age_rating_column = "Age rating"  # Replace with actual column name
            if age_rating_column in row:
                age_rating = row[age_rating_column]
                if isinstance(age_rating, str):
                    matched = False
                    for keyword, desc in content_descriptors.items():
                        if keyword.lower() in age_rating.lower():
                            row[age_rating_column] = desc["age_rating_id"]  # Set Age rating ID
                            logs.append({
                                "line": row_index + 1,
                                "column": age_rating_column,
                                "old": age_rating,
                                "new": desc["age_rating_id"],
                                "reason": f"CDs Found - Content Descriptor: {keyword}"
                            })
                            matched = True
                            break
                    if not matched:
                        row[age_rating_column] = default_age_rating_id
                        logs.append({
                            "line": row_index + 1,
                            "column": age_rating_column,
                            "old": age_rating,
                            "new": default_age_rating_id,
                            "reason": "No relevant descriptor found"
                        })

            # Removing invalid characters from the "Other title names" column
            other_title_column = "Other title names"  # Replace with actual column name
            if other_title_column in row:
                original_title = row[other_title_column]
                if isinstance(original_title, str):
                    # Removing Japanese, Chinese, Russian characters
                    cleaned_title = re.sub(r'[^\x00-\x7F]+', '', original_title)
                    if cleaned_title != original_title:
                        row[other_title_column] = cleaned_title
                        logs.append({
                            "line": row_index + 1,
                            "column": other_title_column,
                            "old": original_title,
                            "new": cleaned_title,
                            "message": "Removed invalid characters (Japanese, Chinese, Russian)"
                        })

        return logs
    except Exception as e:
        return [{"error": str(e)}]


# Route for homepage
@app.route('/')
def index():
    return render_template('index.html')


# Route for file upload
@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

        try:
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            file.save(file_path)

            # Process the file and get logs
            logs = process_file(file_path)
            return jsonify(logs)

        except Exception as e:
            return jsonify({"error": f"Error saving file: {str(e)}"}), 500
    
    return jsonify({"error": "Invalid file format or file too large"}), 400


if __name__ == '__main__':
    # Ensure the upload folder exists
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.run(debug=True)
