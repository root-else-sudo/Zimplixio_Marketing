# emails_fetch.py
# Fetches emails from authorized senders via Gmail API
# Authorized senders: dan@tldrnewsletter.com, noreply@cymru.com
# Outputs: list of email dicts saved to tmp/emails_raw.json

import os
import json
from googleapiclient.discovery import build
from dotenv import load_dotenv
from utils.gmail_auth import get_gmail_credentials

load_dotenv()

# Scopes define what access we need — read-only is enough
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

AUTHORIZED_SENDERS = [
    'dan@tldrnewsletter.com',
    'noreply@cymru.com'
]

CREDENTIALS_FILE = 'credentials.json'
TOKEN_FILE = 'token.json'
OUTPUT_FILE = 'tmp/emails_raw.json'


def authenticate():
    """Authenticate with Gmail API and return service object."""
    creds = get_gmail_credentials(SCOPES, token_file=TOKEN_FILE, credentials_file=CREDENTIALS_FILE)
    return build('gmail', 'v1', credentials=creds)


def fetch_emails(service, max_results=10):
    """Fetch recent emails from authorized senders only."""
    emails = []

    for sender in AUTHORIZED_SENDERS:
        query = f'from:{sender}'
        result = service.users().messages().list(
            userId='me',
            q=query,
            maxResults=max_results
        ).execute()

        messages = result.get('messages', [])

        for msg in messages:
            msg_data = service.users().messages().get(
                userId='me',
                id=msg['id'],
                format='full'
            ).execute()

            headers = msg_data['payload']['headers']
            subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
            sender_email = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown')
            date = next((h['value'] for h in headers if h['name'] == 'Date'), 'Unknown')

            emails.append({
                'id': msg['id'],
                'sender': sender_email,
                'subject': subject,
                'date': date,
                'snippet': msg_data.get('snippet', '')
            })

    return emails


def main():
    """Main entry point."""
    print("Authenticating with Gmail API...")
    service = authenticate()

    print("Fetching emails from authorized senders...")
    emails = fetch_emails(service)

    # Save to tmp/
    os.makedirs('tmp', exist_ok=True)
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(emails, f, indent=2)

    print(f"Done. {len(emails)} emails saved to {OUTPUT_FILE}")


if __name__ == '__main__':
    main()