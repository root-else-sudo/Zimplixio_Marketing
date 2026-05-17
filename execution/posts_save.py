# posts_save.py
# Saves each draft LinkedIn post from tmp/posts_draft.json as its own .md file.
# Files land in posts/YYYY-MM/YYYY-MM-DD/ using the post's source date.
# Input:  tmp/posts_draft.json
# Output: individual .md files under posts/

import json
import os
import re
from datetime import datetime, timezone

INPUT_FILE = 'tmp/posts_draft.json'
POSTS_ROOT = 'posts'


def parse_date(date_str: str) -> datetime:
    """Parse ISO 8601 date string, fall back to today on failure."""
    try:
        return datetime.fromisoformat(date_str)
    except Exception:
        return datetime.now(timezone.utc)


def slugify(text: str) -> str:
    """Convert text to a safe filename slug."""
    text = text.lower()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_-]+', '-', text)
    return text[:50].strip('-')


def newsletter_slug(newsletter: str) -> str:
    """Shorten newsletter name for use in filename."""
    return slugify(newsletter.replace('DragonNews Bytes', 'dnb').replace('TLDR ', 'tldr-'))


def build_filepath(post: dict) -> str:
    """Build the full file path for a post."""
    dt = parse_date(post.get('source_date', ''))
    month_folder = dt.strftime('%Y-%m')
    day_folder = dt.strftime('%Y-%m-%d')

    n_slug = newsletter_slug(post.get('newsletter', 'unknown'))
    story_slug = post.get('slug') or slugify(post.get('source_subject', 'post'))
    filename = f"{dt.strftime('%Y-%m-%d')}_{n_slug}_{story_slug}.md"

    return os.path.join(POSTS_ROOT, month_folder, day_folder, filename)


def build_md_content(post: dict) -> str:
    """Render the post as plain content — no metadata header."""
    return post.get('post', '') + '\n'


def main():
    if not os.path.exists(INPUT_FILE):
        print(f"ERROR: {INPUT_FILE} not found. Run posts_generate.py first.")
        return

    with open(INPUT_FILE, 'r') as f:
        drafts = json.load(f)

    if not isinstance(drafts, list) or len(drafts) == 0:
        print("ERROR: No drafts to save.")
        return

    saved = []
    errors = []

    for post in drafts:
        try:
            filepath = build_filepath(post)
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            content = build_md_content(post)

            with open(filepath, 'w') as f:
                f.write(content)

            saved.append(filepath)
            print(f"  Saved: {filepath}")
        except Exception as e:
            errors.append({'id': post.get('id', '?'), 'error': str(e)})
            print(f"  WARN: Failed to save post {post.get('id', '?')}: {e}")

    print(f"\nDone. {len(saved)} posts saved, {len(errors)} errors.")


if __name__ == '__main__':
    main()
