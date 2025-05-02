#!/usr/bin/env python
import sys
import os
from dotenv import load_dotenv  # Import load_dotenv
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))  # DON'T CHANGE THIS !!!

# Load environment variables from .env file
load_dotenv()

from flask import Flask, request, jsonify, render_template
import requests
from requests.auth import HTTPBasicAuth
import json
import ollama
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)

app = Flask(__name__, static_folder='static', static_url_path='')


# === Serve the HTML page ===
@app.route('/')
def index():
    # Serve the main HTML file from the static folder
    return app.send_static_file('index.html')

# === API Endpoint to Create Jira Issue ===
@app.route('/api/create_jira', methods=['POST'])
def create_jira_issue():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid JSON payload'}), 400

    # Extract data from frontend
    jira_url = data.get('jira_url')
    jira_email = data.get('jira_email')
    api_token = data.get('api_token')
    project_key = data.get('project_key')
    issue_summary = data.get('issue_summary')
    issue_type = data.get('issue_type')
    # ollama_url = data.get('ollama_url') # No longer needed from frontend
    ollama_prompt = data.get('ollama_prompt')

    # Get Ollama host from environment variable
    ollama_host = os.getenv('OLLAMA_HOST')

    # Basic validation - Ensure all fields including ollama_host are present
    required_fields = [jira_url, jira_email, api_token, project_key, issue_summary, issue_type, ollama_host, ollama_prompt]
    field_names = ['jira_url', 'jira_email', 'api_token', 'project_key', 'issue_summary', 'issue_type', 'OLLAMA_HOST (in .env)', 'ollama_prompt']
    if not all(required_fields):
        missing = [name for name, val in zip(field_names, required_fields) if not val]
        return jsonify({'error': f"Missing required fields: {','.join(missing)}"}), 400

    # Ensure Jira URL ends with a slash for consistency
    if not jira_url.endswith('/'):
        jira_url += '/'
    jira_api_url = f'{jira_url}rest/api/2/issue/'

    try:
        # === Step 1: Use Ollama (at OLLAMA_HOST from .env) to generate description ===
        logging.info(f'Connecting to Ollama at: {ollama_host}')
        # Create an Ollama client pointing to the host from .env
        try:
            # Ensure the URL has a scheme (like http://)
            if not ollama_host.startswith(('http://', 'https://')):
                ollama_host_url = 'http://' + ollama_host  # Default to http if no scheme
            else:
                ollama_host_url = ollama_host

            client = ollama.Client(host=ollama_host_url)
            # Verify connection by listing models (optional, but good practice)
            client.list()
            logging.info(f'Successfully connected to Ollama at {ollama_host_url}')
        except Exception as conn_err:
            logging.error(f'Failed to connect to Ollama at {ollama_host_url}: {conn_err}')
            return jsonify({'error': f'Could not connect to Ollama specified in OLLAMA_HOST ({ollama_host_url}). Please ensure it is running and accessible. Error: {conn_err}'}), 500

        logging.info(f'Generating description with Ollama using prompt: {ollama_prompt[:100]}...')
        # Use the client connected to the user's Ollama instance
        ollama_response = client.generate(model='llama3.2', prompt=ollama_prompt)  # Assuming orca-mini is available on user's instance
        description = ollama_response['response']
        logging.info('Ollama description generated successfully.')

        # === Step 2: Create Jira ticket ===
        auth = HTTPBasicAuth(jira_email, api_token)
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }
        payload = json.dumps({
            'fields': {
                'project': {
                    'key': project_key
                },
                'summary': issue_summary,
                'description': description,
                'issuetype': {
                    'name': issue_type
                }
            }
        })

        logging.info(f'Sending request to Jira API: {jira_api_url}')
        response = requests.post(jira_api_url, data=payload, headers=headers, auth=auth)
        logging.info(f'Jira API response status: {response.status_code}')

        response_data = {}
        try:
            response_data = response.json()
            # Check for specific Jira errors in the response
            if response.status_code >= 400 and 'errorMessages' in response_data:
                # FIXED: Use double quotes for the f-string or for the key
                logging.error(f"Jira API Error: {response_data['errorMessages']}")
            if response.status_code >= 400 and 'errors' in response_data:
                logging.error(f"Jira API Field Errors: {response_data['errors']}")

        except json.JSONDecodeError:
            logging.error(f'Failed to decode Jira API JSON response. Status: {response.status_code}, Body: {response.text}')
            response_data = {'error': 'Failed to decode Jira response', 'text': response.text}

        # Return Jira's response regardless of status code, frontend handles display
        return jsonify({
            'status_code': response.status_code,
            'response': response_data
        }), response.status_code

    except ollama.ResponseError as e:
        logging.error(f'Ollama API error during generation: {e} (Host: {ollama_host_url})', exc_info=True)
        return jsonify({'error': f'Ollama API error: {e.error} (using {ollama_host_url})'}), 500
    except requests.exceptions.RequestException as e:
        # Catch connection errors for Jira API
        logging.error(f'Jira API request failed: {e}', exc_info=True)
        return jsonify({'error': f'Jira API request failed: Could not connect to {jira_api_url}. Details: {e}'}), 500
    except Exception as e:
        logging.error(f'An unexpected error occurred: {e}', exc_info=True)
        return jsonify({'error': f'An unexpected server error occurred: {e}'}), 500

if __name__ == '__main__':
    # Run on 0.0.0.0 to be accessible from network if needed
    # Debug mode should be off for typical local running, but can be enabled for troubleshooting
    app.run(host='0.0.0.0', port=8000, debug=False)
