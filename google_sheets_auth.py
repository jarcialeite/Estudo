import os
import requests
import gspread
from google.oauth2.credentials import Credentials


def get_access_token():
    """Get access token from Replit connector."""
    hostname = os.environ.get('REPLIT_CONNECTORS_HOSTNAME')
    
    repl_identity = os.environ.get('REPL_IDENTITY')
    web_repl_renewal = os.environ.get('WEB_REPL_RENEWAL')
    
    if repl_identity:
        x_replit_token = f'repl {repl_identity}'
    elif web_repl_renewal:
        x_replit_token = f'depl {web_repl_renewal}'
    else:
        raise Exception('X_REPLIT_TOKEN not found for repl/depl')
    
    response = requests.get(
        f'https://{hostname}/api/v2/connection?include_secrets=true&connector_names=google-sheet',
        headers={
            'Accept': 'application/json',
            'X_REPLIT_TOKEN': x_replit_token
        }
    )
    
    data = response.json()
    connection_settings = data.get('items', [{}])[0] if data.get('items') else None
    
    if not connection_settings:
        raise Exception('Google Sheet not connected')
    
    settings = connection_settings.get('settings', {})
    access_token = settings.get('access_token') or settings.get('oauth', {}).get('credentials', {}).get('access_token')
    
    if not access_token:
        raise Exception('Google Sheet access token not found')
    
    return access_token


def get_gspread_client():
    """Get gspread client using Replit connector authentication."""
    access_token = get_access_token()
    
    credentials = Credentials(
        token=access_token,
        scopes=[
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive.file',
            'https://www.googleapis.com/auth/drive.appdata',
            'https://www.googleapis.com/auth/spreadsheets.readonly'
        ]
    )
    
    client = gspread.authorize(credentials)
    return client
