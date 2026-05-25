# emails_organize.py
# Marks emails from authorized senders as read and moves them to the correct Gmail label.
# Routing rules:
#   dan@tldrnewsletter.com  → Education/TLDR
#   noreply@cymru.com       → Education/Dragon CyberSecurity
#
# Safe to run multiple times — already-organized emails are skipped.
# Handles backlog (all emails) and new daily emails.
# Uses gmail.modify scope via a separate token (token_modify.json).

import os
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from utils.gmail_auth import get_gmail_credentials

SCOPES = ['https://www.googleapis.com/auth/gmail.modify']
CREDENTIALS_FILE = 'credentials.json'
TOKEN_FILE = 'token_modify.json'

AUTHORIZED_SENDERS = {
    'dan@tldrnewsletter.com': 'Education/TLDR',
    'noreply@cymru.com':      'Dragron CyberSecurity',
}

# Gmail applies labels in bulk up to 1000 ids per request
BATCH_SIZE = 500


def authenticate():
    """Authenticate with gmail.modify scope and return service object."""
    creds = get_gmail_credentials(SCOPES, token_file=TOKEN_FILE, credentials_file=CREDENTIALS_FILE)
    return build('gmail', 'v1', credentials=creds)


def get_or_create_label(service, name: str) -> str:
    """Return the label ID for a given name, creating it if it doesn't exist."""
    existing = service.users().labels().list(userId='me').execute().get('labels', [])
    for label in existing:
        if label['name'].lower() == name.lower():
            return label['id']

    # Create the label (Gmail handles nested names with / automatically)
    created = service.users().labels().create(
        userId='me',
        body={
            'name': name,
            'labelListVisibility': 'labelShow',
            'messageListVisibility': 'show',
        }
    ).execute()
    print(f"  Created label: {name}")
    return created['id']


def fetch_all_message_ids(service, sender_email: str) -> list:
    """Fetch all message IDs from a given sender (handles pagination)."""
    ids = []
    query = f'from:{sender_email}'
    page_token = None

    while True:
        params = {'userId': 'me', 'q': query, 'maxResults': 500}
        if page_token:
            params['pageToken'] = page_token

        result = service.users().messages().list(**params).execute()
        messages = result.get('messages', [])
        ids.extend(m['id'] for m in messages)

        page_token = result.get('nextPageToken')
        if not page_token:
            break

    return ids


def batch_modify(service, message_ids: list, add_label_ids: list, remove_label_ids: list):
    """Apply label changes to a list of message IDs in batches."""
    for i in range(0, len(message_ids), BATCH_SIZE):
        chunk = message_ids[i:i + BATCH_SIZE]
        service.users().messages().batchModify(
            userId='me',
            body={
                'ids': chunk,
                'addLabelIds': add_label_ids,
                'removeLabelIds': remove_label_ids,
            }
        ).execute()


def main():
    print("Authenticating with Gmail (modify scope)...")
    service = authenticate()

    # Ensure target labels exist
    print("Checking labels...")
    label_ids = {}
    for sender, label_name in AUTHORIZED_SENDERS.items():
        label_ids[sender] = get_or_create_label(service, label_name)
        print(f"  {label_name} → {label_ids[sender]}")

    # UNREAD and INBOX label IDs are system labels with fixed names
    total_processed = 0

    for sender, label_name in AUTHORIZED_SENDERS.items():
        print(f"\nFetching all emails from {sender}...")
        message_ids = fetch_all_message_ids(service, sender)
        print(f"  Found {len(message_ids)} emails")

        if not message_ids:
            continue

        print(f"  Marking as read, applying '{label_name}', removing from inbox...")
        try:
            batch_modify(
                service,
                message_ids,
                add_label_ids=[label_ids[sender]],
                remove_label_ids=['UNREAD', 'INBOX'],
            )
            total_processed += len(message_ids)
            print(f"  Done — {len(message_ids)} emails organized")
        except HttpError as e:
            print(f"  ERROR processing {sender}: {e}")

    print(f"\nDone. {total_processed} emails organized in total.")


if __name__ == '__main__':
    main()
