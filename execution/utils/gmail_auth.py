import os
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request


def get_gmail_credentials(scopes, token_file=None, credentials_file=None):
    # Production: env vars set → use them directly
    if os.environ.get('GMAIL_CLIENT_ID'):
        is_modify = any('modify' in s for s in scopes)
        token_key = 'GMAIL_REFRESH_TOKEN_MODIFY' if is_modify else 'GMAIL_REFRESH_TOKEN_READONLY'
        refresh_token = os.environ.get(token_key)
        if not refresh_token:
            raise EnvironmentError(f"{token_key} is not set")
        return Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri='https://oauth2.googleapis.com/token',
            client_id=os.environ['GMAIL_CLIENT_ID'],
            client_secret=os.environ['GMAIL_CLIENT_SECRET'],
            scopes=scopes,
        )
    # Local dev: file-based flow (existing behavior preserved)
    creds = None
    if token_file and os.path.exists(token_file):
        creds = Credentials.from_authorized_user_file(token_file, scopes)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(credentials_file, scopes)
            creds = flow.run_local_server(port=0)
        if token_file:
            with open(token_file, 'w') as f:
                f.write(creds.to_json())
    return creds
