# --- START OF FILE google_calendar_setup.py ---

import os
import pickle
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from config_loader import load_config # Import the loader

# Load configuration
try:
    config = load_config()
    google_auth_config = config.get('google_auth', {})
except Exception as e:
    print(f"FATAL: Could not load configuration for Google Calendar setup: {e}")
    # If config fails to load here, we can't proceed.
    # We'll let it raise an error or define defaults / exit.
    # For simplicity, we'll assume it loads or exits.
    # In a real app, you might have fallback or more graceful exit.
    # Fallback to hardcoded if necessary, but ideally config should exist
    google_auth_config = { 
        "scopes": ["https://www.googleapis.com/auth/calendar"],
        "token_path": "token.json",
        "credentials_path": "credentials.json",
        "redirect_uri": "http://localhost:8080/",
        "server_port": 8080
    }
    print("Warning: Using fallback Google Auth config due to load error.")


# Use values from config
SCOPES = google_auth_config.get('scopes', ['https://www.googleapis.com/auth/calendar'])
TOKEN_PATH = google_auth_config.get('token_path', 'token.json')
CREDENTIALS_PATH = google_auth_config.get('credentials_path', 'credentials.json')
REDIRECT_URI = google_auth_config.get('redirect_uri', 'http://localhost:8080/')
SERVER_PORT = google_auth_config.get('server_port', 8080)


def authenticate_google_calendar():
    """
    Authenticates with the Google Calendar API.
    
    It attempts to load existing credentials from TOKEN_PATH.
    If expired, it refreshes the token. If no valid token exists,
    it initiates the OAuth 2.0 flow to obtain new credentials via a local server.
    
    Returns:
        googleapiclient.discovery.Resource: A Google Calendar API service object if authentication is successful,
                                           otherwise None.
    """
    creds = None
    if os.path.exists(TOKEN_PATH):
        with open(TOKEN_PATH, 'rb') as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                print(f"Error refreshing token: {e}")
                print(f"Deleting problematic {TOKEN_PATH} and asking for new authorization.")
                if os.path.exists(TOKEN_PATH):
                    os.remove(TOKEN_PATH)
                creds = None
        
        if not creds: 
            if not os.path.exists(CREDENTIALS_PATH):
                print(f"Error: {CREDENTIALS_PATH} not found. Please ensure it's in the correct location and defined in config.json.")
                return None
            flow = InstalledAppFlow.from_client_secrets_file(
                CREDENTIALS_PATH, SCOPES)
            flow.redirect_uri = REDIRECT_URI
            creds = flow.run_local_server(port=SERVER_PORT)
        
        with open(TOKEN_PATH, 'wb') as token:
            pickle.dump(creds, token)

    try:
        service = build('calendar', 'v3', credentials=creds)
        print("Successfully connected to Google Calendar API.")
        return service
    except HttpError as error:
        print(f'An API error occurred: {error}')
        return None
    except Exception as e:
        print(f'An unexpected error occurred during service build: {e}')
        return None

if __name__ == '__main__':
    service = authenticate_google_calendar()
    if service:
        print("Google Calendar service authenticated and built successfully.")
    else:
        print("Failed to authenticate and build Google Calendar service.")
        
# --- END OF FILE google_calendar_setup.py ---