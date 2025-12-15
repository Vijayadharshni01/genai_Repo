from flask import Flask, request, jsonify, send_file, Response
import os
import tempfile
import json
import uuid
import shutil
from dotnet_to_springboot import unzip_and_convert_stream

app = Flask(__name__)

# Store temporary file paths: { download_id: zip_path }
TEMP_ZIPS = {}

@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

@app.route('/api/convert-stream', methods=['POST'])
def convert_project_stream():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    # Use temp directory for processing (not saving locally permanently)
    temp_dir = tempfile.mkdtemp()
    zip_path = os.path.join(temp_dir, file.filename)
    file.save(zip_path)
    
    extract_folder = os.path.join(temp_dir, "extract")
    output_folder = os.path.join(temp_dir, "springboot_output")
    
    def generate():
        try:
            # Iterate over the generator from the conversion script
            for result in unzip_and_convert_stream(zip_path, extract_folder, output_folder):
                
                # Check if this is the completion message
                if result['type'] == 'complete':
                    # Generate a unique ID for download
                    download_id = str(uuid.uuid4())
                    zip_file_path = result['zip_path']
                    
                    # Store in global dict for later retrieval
                    TEMP_ZIPS[download_id] = zip_file_path
                    
                    # Send completion message with download ID
                    yield json.dumps({
                        'type': 'complete',
                        'downloadId': download_id
                    }) + "\n"
                else:
                    # Stream normal file result
                    yield json.dumps(result) + "\n"
                    
        except Exception as e:
            print(f"Stream error: {e}")
            yield json.dumps({'type': 'error', 'message': str(e)}) + "\n"
        
        # Cleanup is tricky here because we need the zip file to persist for download.
        # We can rely on OS temp cleaning or implement a cleanup Cron.
        # For now, we leave the temp dir.

    return Response(generate(), mimetype='application/x-ndjson')

@app.route('/api/download/<download_id>')
def download_zip_by_id(download_id):
    if download_id in TEMP_ZIPS:
        file_path = TEMP_ZIPS[download_id]
        if os.path.exists(file_path):
            return send_file(file_path, as_attachment=True, download_name='springboot-project.zip')
    
    return jsonify({'error': 'File not found or expired'}), 404

if __name__ == '__main__':
    app.run(debug=True, port=5000)