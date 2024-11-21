from flask import Flask, request, jsonify
import polars as pl
import logging

app = Flask(__name__)

# Configure logging
logging.basicConfig(
    filename='report.log',
    format='%(asctime)s %(levelname)s %(message)s',
    level=logging.INFO
)

def process_csv(data):
    df = pl.read_csv(data)

    # 1. Duplicate Check
    duplicates = df.groupby('GTI').count().filter(pl.col('count') > 1)
    if not duplicates.is_empty():
        logging.warning(f"Duplicate GTIs found: {duplicates.to_dict(orient='records')}")
        yield f"**Warning:** Duplicate GTIs found.\n"

    # 2. Age Rating ID Auto-Fill
    df = df.with_column(
        pl.when(pl.col('Content Descriptors').str.contains('General|Very mild'))
        .then(2)
        .when(pl.col('Content Descriptors').str.contains('Mild'))
        .then(9)
        .when(pl.col('Content Descriptors').str.contains('Strong'))
        .then(156)
        .when(pl.col('Content Descriptors').str.contains('High impact'))
        .then(154)
        .otherwise(147)
        .fill_null(147)
        .alias('Age Rating ID')
    )

    # 3. Character Validation
    invalid_chars_regex = r'[^\x00-\x7F]'  # Regex for non-ASCII characters
    df = df.with_column(
        pl.col('Other title names').str.replace_all(invalid_chars_regex, '').alias('Other title names')
    )

    # Log changes
    for idx, row in df.iterrows():
        original_age_rating = row['Age Rating ID'] if 'Age Rating ID' in row else None
        original_title = row['Other title names'] if 'Other title names' in row else None
        if row['Age Rating ID'] != original_age_rating:
            logging.info(f"Age rating changed for row {idx+1}: {original_age_rating} -> {row['Age Rating ID']}")
            yield f"**Info:** Age rating changed for row {idx+1}.\n"
        if row['Other title names'] != original_title:
            logging.info(f"Invalid characters removed from row {idx+1}: {original_title} -> {row['Other title names']}")
            yield f"**Info:** Invalid characters removed from row {idx+1}.\n"

    # Write the processed DataFrame to a new CSV (optional)
    # df.write_csv('processed.csv')

    yield "**Processing Completed.**\n"  # Final success message


@app.route('/process', methods=['POST'])
def process_csv_api():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    file = request.files['file']
    if not file.filename.endswith('.csv'):
        return jsonify({'error': 'Invalid file format. Please upload a CSV file.'}), 400

    try:
        # Generate logs in chunks for live updates
        logs = process_csv(file.stream)
        return jsonify({'logs': next(logs)})  # Send initial log
    except Exception as e:
        logging.error(f"Error processing CSV: {e}")
        return jsonify({'error': 'An error occurred during processing.'}), 500

    # Use a generator to yield logs in chunks and return them as the request progresses
    for log in logs:
        yield f"data:{log}\n\n"  # Send subsequent logs as events with newline


if __name__ == '__main__':
    app.run(debug=True)
