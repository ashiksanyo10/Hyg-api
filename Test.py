from flask import Flask, request, jsonify, render_template
import polars as pl
import re

app = Flask(__name__)

# Default Age Rating ID
DEFAULT_AGE_RATING = 147  # Default Age Rating if no keyword matches

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    # Handle file upload
    file = request.files['file']
    df = pl.read_csv(file)

    logs = []  # Collect logs here

    # Check for blanks in the dataframe
    for col in df.columns:
        null_rows = df.filter(df[col].is_null()).to_dicts()
        for row in null_rows:
            logs.append({
                "line": row.get("line", "unknown"),
                "column": col,
                "issue": "Blank value found"
            })

    # Update Age rating based on the "Content Descriptor" column
    if "Age rating" in df.columns and "Content Descriptor" in df.columns:
        for idx, (age, descriptor) in enumerate(zip(df["Age rating"], df["Content Descriptor"])):
            new_age = DEFAULT_AGE_RATING  # Default age rating if no content descriptor matches
            reason = f"Content Descriptor value: {descriptor}"  # Default reason to the content descriptor

            if descriptor:  # Ensure the descriptor is not empty
                # Logic for determining the new age rating based on Content Descriptor
                if "general" in descriptor.lower() or "very mild" in descriptor.lower():
                    new_age = 2
                elif "mild" in descriptor.lower():
                    new_age = 9
                elif "strong" in descriptor.lower():
                    new_age = 156
                elif "high impact" in descriptor.lower():
                    new_age = 154
                else:
                    new_age = DEFAULT_AGE_RATING  # If no match, keep the default age rating

            # If the age rating has changed, log the change
            if age != new_age:  # Log changes only if there is a modification
                logs.append({
                    "line": idx + 1,
                    "column": "Age rating",
                    "old": age,
                    "new": new_age,
                    "reason": reason
                })
                df[idx, "Age rating"] = new_age

    # Remove invalid characters (Japanese, Chinese, Russian) from "Other title names"
    if "Other title names" in df.columns:
        def clean_invalid_chars(text):
            cleaned_text = re.sub(r'[\u4E00-\u9FFF\u3040-\u30FF\u0400-\u04FF]', '', text)
            removed = ''.join(set(text) - set(cleaned_text))
            return cleaned_text, removed

        for idx, value in enumerate(df["Other title names"]):
            if isinstance(value, str):
                cleaned_value, removed_chars = clean_invalid_chars(value)
                if removed_chars:
                    logs.append({
                        "line": idx + 1,
                        "column": "Other title names",
                        "removed": removed_chars
                    })
                df[idx, "Other title names"] = cleaned_value

    # Return logs in JSON format
    return jsonify(logs)

if __name__ == "__main__":
    app.run(debug=True)
