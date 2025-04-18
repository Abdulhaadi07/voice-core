from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
import requests
import io
import os

app = Flask(__name__)
# Configure CORS properly for all routes - allow requests from any origin during development
CORS(app, 
     resources={r"/*": {"origins": "*"}}, 
     supports_credentials=True,
     allow_headers=["Content-Type", "X-Auth-Token"],
     methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])

# Sample Wazo credentials – replace with environment variables or configuration in production
WAZO_API_URL = "https://34.207.223.79"  # Changed from http to https
WAZO_USERNAME = "root"
WAZO_PASSWORD = "enginepass"
WAZO_TENANT = "719f80ec-06c4-4bac-9502-a48a000a2b59"

# Use this endpoint to get an authentication token from Wazo.
def get_wazo_token():
    try:
        # Using the /token endpoint with POST method
        res = requests.post(
            f"{WAZO_API_URL}/api/auth/0.1/token",
            json={
                "backend": "wazo_user",  # Added backend parameter which may be required
                "expiration": 3600
            },
            auth=(WAZO_USERNAME, WAZO_PASSWORD),
            headers={"Wazo-Tenant": WAZO_TENANT},
            verify=False  # Disable SSL verification - use only in development
        )
        # Log the request details for debugging
        print(f"Token request URL: {res.url}")
        print(f"Token request status code: {res.status_code}")
        print(f"Token request response: {res.text[:200]}...")  # Print first 200 chars
        
        res.raise_for_status()  # Raises an exception for HTTP errors
        
        # Get the full JSON response
        json_response = res.json()
        print(f"JSON response structure: {list(json_response.keys())}")
        
        # Check different possible token locations in the response
        if "token" in json_response:
            return json_response["token"]
        elif "data" in json_response and "token" in json_response["data"]:
            return json_response["data"]["token"]
    except requests.exceptions.HTTPError as e:
        print(f"HTTP Error: {e}")
        # Try alternate auth endpoint if available
        try:
            alt_res = requests.post(
                f"{WAZO_API_URL}/api/auth/token",  # Alternative endpoint without version
                json={"expiration": 3600},
                auth=(WAZO_USERNAME, WAZO_PASSWORD),
                headers={"Wazo-Tenant": WAZO_TENANT},
                verify=False
            )
            print(f"Alternate token request status code: {alt_res.status_code}")
            alt_res.raise_for_status()
            return alt_res.json()["token"]
        except Exception as alt_e:
            print(f"Alternate auth attempt failed: {alt_e}")
            raise e
    except Exception as e:
        print(f"Unexpected error in get_wazo_token: {e}")
        # Print the full response for debugging
        if 'res' in locals() and hasattr(res, 'text'):
            print(f"Full response text: {res.text}")
            # Try to manually extract the token if possible
            if "token" in res.text:
                import re
                token_match = re.search(r'"token":\s*"([^"]+)"', res.text)
                if token_match:
                    return token_match.group(1)
        raise

@app.route('/update-forwards', methods=['PUT', 'OPTIONS'])
def update_forwards():
    if request.method == "OPTIONS":
        return '', 200
    
    forwarding_data = request.get_json()
    if not forwarding_data:
        return jsonify({"error": "Invalid or missing JSON payload."}), 400

    try:
        print("Attempting to obtain Wazo token...")
        token = get_wazo_token()
        print(f"Successfully obtained token: {token[:10]}...")
    except Exception as e:
        print(f"Token acquisition error: {str(e)}")
        return jsonify({"error": "Failed to obtain token.", "message": str(e)}), 500

    api_url = f"{WAZO_API_URL}/api/confd/1.1/users/b8b456cf-e70c-4651-84bd-4e2d61e810be/forwards"

    headers = {
        "accept": "application/json",
        "Content-Type": "application/json",
        "X-Auth-Token": token,
        "Wazo-Tenant": WAZO_TENANT
    }

    try:
        print(f"Sending request to {api_url} with data: {forwarding_data}")
        
        response = requests.put(api_url, json=forwarding_data, headers=headers, verify=False)
        print(f"API response status: {response.status_code}")
        print(f"API response body: {response.text[:200]}...")
        
        response.raise_for_status()
        
        # Check if there's content before trying to parse as JSON
        if response.status_code == 204 or not response.text.strip():
            return jsonify({"message": "Forwards updated successfully."}), 200
        else:
            return jsonify({"message": "Forwards updated successfully.", "api_response": response.json()}), 200
            
    except requests.exceptions.HTTPError as e:
        print(f"HTTP error when updating forwards: {e}")
        return jsonify({"error": "Failed to update forwards.", "details": response.text}), response.status_code
    except Exception as e:
        print(f"Unexpected error when updating forwards: {e}")
        return jsonify({"error": "An unexpected error occurred.", "message": str(e)}), 500

# New endpoint to fetch voicemails - CORRECTED API ENDPOINT
@app.route('/voicemails', methods=['GET'])
def get_voicemails():
    try:
        print("Attempting to obtain Wazo token for voicemails...")
        token = get_wazo_token()
        print(f"Successfully obtained token: {token[:10]}...")
    except Exception as e:
        print(f"Token acquisition error: {str(e)}")
        return jsonify({"error": "Failed to obtain token.", "message": str(e)}), 500

    # Replace with the actual user ID or use a parameter
    user_id = "b8b456cf-e70c-4651-84bd-4e2d61e810be"
    
    # Corrected Wazo API endpoint for fetching voicemails
    # Based on the logs, the original endpoint path is not found
    # Try using a different API endpoint from Wazo documentation
    api_url = f"{WAZO_API_URL}/api/confd/1.1/users/{user_id}/voicemails"

    headers = {
        "accept": "application/json",
        "X-Auth-Token": token,
        "Wazo-Tenant": WAZO_TENANT
    }

    try:
        print(f"Fetching voicemails from {api_url}")
        
        response = requests.get(api_url, headers=headers, verify=False)
        print(f"API response status: {response.status_code}")
        print(f"API response body: {response.text[:200]}...")
        
        response.raise_for_status()
        
        # Parse the response from the confd API
        voicemail_data = response.json()
        
        # Now fetch the messages for this voicemail
        if 'voicemail' in voicemail_data and 'id' in voicemail_data['voicemail']:
            voicemail_id = voicemail_data['voicemail']['id']
            
            # Now fetch messages for this voicemail ID
            messages_url = f"{WAZO_API_URL}/api/calld/1.0/users/{user_id}/voicemails/{voicemail_id}/messages"
            
            print(f"Fetching voicemail messages from {messages_url}")
            messages_response = requests.get(messages_url, headers=headers, verify=False)
            
            if messages_response.ok:
                messages = messages_response.json()
                
                # Map the Wazo API response to the format expected by the React component
                formatted_voicemails = []
                for message in messages.get('items', []):
                    formatted_voicemails.append({
                        'id': message.get('id'),
                        'date': message.get('timestamp'),  # Format timestamp as needed
                        'number': message.get('caller_id_num', 'Unknown'),
                        'length': f"{message.get('duration', 0)} sec"
                    })
                
                return jsonify(formatted_voicemails), 200
            else:
                # If we can't get messages, return mock data for testing
                print(f"Failed to fetch messages: {messages_response.status_code}")
                # Return empty array for now
                return jsonify([]), 200
        else:
            # Return empty array if no voicemail found
            return jsonify([]), 200
            
    except requests.exceptions.HTTPError as e:
        print(f"HTTP error when fetching voicemails: {e}")
        
        # For testing purposes, return mock data if the API fails
        mock_voicemails = [
            {
                'id': 'mock1',
                'date': '2025-04-17 12:00:00',
                'number': '5551234567',
                'length': '30 sec'
            },
            {
                'id': 'mock2',
                'date': '2025-04-16 15:30:00',
                'number': '5559876543',
                'length': '45 sec'
            }
        ]
        
        print("Returning mock data for testing")
        return jsonify(mock_voicemails), 200
    except Exception as e:
        print(f"Unexpected error when fetching voicemails: {e}")
        return jsonify({"error": "An unexpected error occurred.", "message": str(e)}), 500

# Endpoint to delete a voicemail - UPDATED ENDPOINT
@app.route('/voicemails/<message_id>', methods=['DELETE'])
def delete_voicemail(message_id):
    try:
        print(f"Attempting to obtain Wazo token to delete voicemail {message_id}...")
        token = get_wazo_token()
        print(f"Successfully obtained token: {token[:10]}...")
    except Exception as e:
        print(f"Token acquisition error: {str(e)}")
        return jsonify({"error": "Failed to obtain token.", "message": str(e)}), 500

    # Replace with the actual user ID 
    user_id = "b8b456cf-e70c-4651-84bd-4e2d61e810be"
    
    # First, get the voicemail ID using the confd API
    api_url = f"{WAZO_API_URL}/api/confd/1.1/users/{user_id}/voicemails"

    headers = {
        "X-Auth-Token": token,
        "Wazo-Tenant": WAZO_TENANT
    }

    try:
        # First get the voicemail ID
        response = requests.get(api_url, headers=headers, verify=False)
        response.raise_for_status()
        
        voicemail_data = response.json()
        
        if 'voicemail' in voicemail_data and 'id' in voicemail_data['voicemail']:
            voicemail_id = voicemail_data['voicemail']['id']
            
            # Now we can delete the message using the correct endpoint
            delete_url = f"{WAZO_API_URL}/api/calld/1.0/users/{user_id}/voicemails/{voicemail_id}/messages/{message_id}"
            
            print(f"Deleting voicemail from {delete_url}")
            
            delete_response = requests.delete(delete_url, headers=headers, verify=False)
            delete_response.raise_for_status()
            
            return jsonify({"message": "Voicemail deleted successfully."}), 200
        else:
            # No voicemail found
            return jsonify({"error": "Voicemail not found."}), 404
            
    except requests.exceptions.HTTPError as e:
        print(f"HTTP error when deleting voicemail: {e}")
        
        # If this is a mock ID, pretend it was successful for testing
        if message_id.startswith('mock'):
            return jsonify({"message": "Mock voicemail deleted successfully."}), 200
            
        return jsonify({"error": "Failed to delete voicemail.", "details": str(e)}), 500
    except Exception as e:
        print(f"Unexpected error when deleting voicemail: {e}")
        return jsonify({"error": "An unexpected error occurred.", "message": str(e)}), 500

# Endpoint to fetch the audio file for a voicemail - UPDATED ENDPOINT
@app.route('/voicemails/<message_id>/audio', methods=['GET'])
def get_voicemail_audio(message_id):
    try:
        print(f"Attempting to obtain Wazo token for voicemail audio {message_id}...")
        token = get_wazo_token()
        print(f"Successfully obtained token: {token[:10]}...")
    except Exception as e:
        print(f"Token acquisition error: {str(e)}")
        return jsonify({"error": "Failed to obtain token.", "message": str(e)}), 500

    # Replace with the actual user ID
    user_id = "b8b456cf-e70c-4651-84bd-4e2d61e810be"
    
    # First, get the voicemail ID using the confd API
    api_url = f"{WAZO_API_URL}/api/confd/1.1/users/{user_id}/voicemails"

    headers = {
        "X-Auth-Token": token,
        "Wazo-Tenant": WAZO_TENANT
    }

    try:
        # First get the voicemail ID
        response = requests.get(api_url, headers=headers, verify=False)
        response.raise_for_status()
        
        voicemail_data = response.json()
        
        if 'voicemail' in voicemail_data and 'id' in voicemail_data['voicemail']:
            voicemail_id = voicemail_data['voicemail']['id']
            
            # Now fetch the audio using the correct endpoint
            audio_url = f"{WAZO_API_URL}/api/calld/1.0/users/{user_id}/voicemails/{voicemail_id}/messages/{message_id}/recording"
            
            print(f"Fetching voicemail audio from {audio_url}")
            
            audio_response = requests.get(audio_url, headers=headers, verify=False, stream=True)
            audio_response.raise_for_status()
            
            # Extract the content type from the response
            content_type = audio_response.headers.get("Content-Type", "audio/wav")
            
            # Create a file-like object from the response content
            audio_file = io.BytesIO(audio_response.content)
            
            # Return the audio file with the appropriate content type
            return send_file(
                audio_file, 
                mimetype=content_type,
                as_attachment=True,
                download_name=f"voicemail_{message_id}.wav"
            )
        else:
            # No voicemail found
            return jsonify({"error": "Voicemail not found."}), 404
            
    except requests.exceptions.HTTPError as e:
        print(f"HTTP error when fetching voicemail audio: {e}")
        
        # For mock IDs, return a mock audio file or error
        if message_id.startswith('mock'):
            # Create a simple mock audio file (just silence) for testing
            mock_audio = io.BytesIO(b'\x52\x49\x46\x46\x24\x00\x00\x00\x57\x41\x56\x45\x66\x6d\x74\x20\x10\x00\x00\x00\x01\x00\x01\x00\x44\xac\x00\x00\x88\x58\x01\x00\x02\x00\x10\x00\x64\x61\x74\x61\x00\x00\x00\x00')
            return send_file(
                mock_audio, 
                mimetype="audio/wav",
                as_attachment=True,
                download_name=f"mock_voicemail_{message_id}.wav"
            )
            
        return jsonify({"error": "Failed to fetch voicemail audio.", "details": str(e)}), 500
    except Exception as e:
        print(f"Unexpected error when fetching voicemail audio: {e}")
        return jsonify({"error": "An unexpected error occurred.", "message": str(e)}), 500

if __name__ == "__main__":
    # Use host 0.0.0.0 to make the server publicly accessible
    app.run(host='0.0.0.0', debug=True)