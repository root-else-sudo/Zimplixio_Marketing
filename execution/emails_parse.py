# emails_parse.py
# Reads tmp/emails_raw.json and normalizes each email into a structured format.
# Handles two sender types: TLDR newsletters and DragonNews Bytes (DNB).
# Output: tmp/emails_parsed.json

import json
import re
import html
import os
import time
from datetime import datetime
from email.utils import parsedate_to_datetime

INPUT_FILE = 'tmp/emails_raw.json'
OUTPUT_FILE = 'tmp/emails_parsed.json'

STALE_THRESHOLD_HOURS = 24

ZERO_WIDTH_SPACES = '‌​‍﻿'


def parse_sender(raw_sender):
    """Split 'Display Name <email@domain.com>' into name and email."""
    match = re.match(r'^(.*?)\s*<([^>]+)>$', raw_sender.strip())
    if match:
        return match.group(1).strip(), match.group(2).strip().lower()
    # Plain email with no display name
    return '', raw_sender.strip().lower()


def clean_snippet(snippet):
    """Remove zero-width spaces and decode HTML entities."""
    cleaned = html.unescape(snippet)
    cleaned = cleaned.translate(str.maketrans('', '', ZERO_WIDTH_SPACES))
    return cleaned.strip()


def parse_date(raw_date):
    """Parse RFC 2822 date string into ISO 8601. Returns raw string on failure."""
    try:
        dt = parsedate_to_datetime(raw_date)
        return dt.isoformat()
    except Exception:
        return raw_date


def parse_dnb_subject(subject):
    """
    Extract category tag from DNB subject lines.
    '[DNB] [MALWARE] Some Title' -> category='MALWARE', title='Some Title'
    """
    # Match all bracketed tags at the start, capture remaining title
    tags = re.findall(r'\[([^\]]+)\]', subject)
    # First tag is always 'DNB', second (if present) is the category
    category = tags[1] if len(tags) >= 2 else 'GENERAL'
    # Title is everything after the last bracketed tag
    title = re.sub(r'^(\s*\[[^\]]+\])+\s*', '', subject).strip()
    return category, title


def parse_dnb_snippet(snippet):
    """
    Extract structured fields from DNB snippet format:
    'Title: ... Source: ... Date Published: ... Excerpt: ...'
    Returns a dict with those fields (all may be empty string if not found).
    """
    def extract_field(text, field_name, next_fields):
        pattern = rf'{re.escape(field_name)}:\s*(.*?)(?=(?:{"|".join(re.escape(f) for f in next_fields)}):|\Z)'
        match = re.search(pattern, text, re.DOTALL)
        return match.group(1).strip() if match else ''

    field_order = ['Title', 'Source', 'Date Published', 'Excerpt']
    result = {}
    for i, field in enumerate(field_order):
        next_fields = field_order[i + 1:]
        result[field.lower().replace(' ', '_')] = extract_field(snippet, field, next_fields)

    return result


def parse_tldr(email):
    """Parse a TLDR newsletter email into a structured dict."""
    sender_name, sender_email = parse_sender(email['sender'])
    return {
        'id': email['id'],
        'type': 'tldr',
        'newsletter': sender_name,  # e.g. 'TLDR AI', 'TLDR InfoSec'
        'sender_email': sender_email,
        'subject': email['subject'],
        'date_raw': email['date'],
        'date': parse_date(email['date']),
        'snippet': clean_snippet(email['snippet']),
    }


def parse_dnb(email):
    """Parse a DragonNews Bytes email into a structured dict."""
    sender_name, sender_email = parse_sender(email['sender'])
    category, article_title = parse_dnb_subject(email['subject'])
    cleaned_snippet = clean_snippet(email['snippet'])
    structured = parse_dnb_snippet(cleaned_snippet)

    return {
        'id': email['id'],
        'type': 'dnb',
        'newsletter': sender_name,
        'sender_email': sender_email,
        'subject': email['subject'],
        'date_raw': email['date'],
        'date': parse_date(email['date']),
        'category': category,
        'article_title': article_title,
        'source': structured.get('source', ''),
        'date_published': structured.get('date_published', ''),
        'excerpt': structured.get('excerpt', ''),
    }


def parse_email(email):
    """Route email to the correct parser based on sender."""
    _, sender_email = parse_sender(email['sender'])
    if sender_email == 'dan@tldrnewsletter.com':
        return parse_tldr(email)
    elif sender_email == 'noreply@cymru.com':
        return parse_dnb(email)
    else:
        # Unknown sender — pass through with minimal structure for logging
        return {
            'id': email['id'],
            'type': 'unknown',
            'sender_email': sender_email,
            'subject': email['subject'],
            'date_raw': email['date'],
            'date': parse_date(email['date']),
            'snippet': clean_snippet(email['snippet']),
        }


def main():
    if not os.path.exists(INPUT_FILE):
        print(f"ERROR: {INPUT_FILE} not found. Run emails_fetch.py first.")
        return

    age_hours = (time.time() - os.path.getmtime(INPUT_FILE)) / 3600
    if age_hours > STALE_THRESHOLD_HOURS:
        print(f"WARN: {INPUT_FILE} is {age_hours:.1f} hours old. Run emails_fetch.py to refresh.")

    with open(INPUT_FILE, 'r') as f:
        raw_emails = json.load(f)

    if not isinstance(raw_emails, list):
        print(f"ERROR: Expected a list in {INPUT_FILE}, got {type(raw_emails).__name__}")
        return

    parsed = []
    errors = []

    for email in raw_emails:
        try:
            parsed.append(parse_email(email))
        except Exception as e:
            errors.append({'id': email.get('id', 'unknown'), 'error': str(e)})
            print(f"  WARN: Failed to parse email {email.get('id', '?')}: {e}")

    os.makedirs('tmp', exist_ok=True)
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(parsed, f, indent=2, ensure_ascii=False)

    print(f"Done. {len(parsed)} emails parsed, {len(errors)} errors. Output: {OUTPUT_FILE}")


if __name__ == '__main__':
    main()
