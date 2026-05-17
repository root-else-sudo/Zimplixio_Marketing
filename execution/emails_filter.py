# emails_filter.py
# Scores parsed emails for relevance to Zimplixio's marketing topics and returns the top stories.
# Relevance is determined by keyword matching on subject + snippet and newsletter type weight.
# Input:  tmp/emails_parsed.json
# Output: tmp/emails_filtered.json

import json
import os
import re

INPUT_FILE = 'tmp/emails_parsed.json'
OUTPUT_FILE = 'tmp/emails_filtered.json'

# How many top stories to keep per run
TOP_N = 2

# Topic keywords relevant to Zimplixio's positioning:
# enterprise tech for SMBs, AI adoption, e-commerce, cybersecurity, cloud/DevOps, business strategy
TOPIC_KEYWORDS = [
    # AI / LLMs / agents
    'ai', 'llm', 'gpt', 'claude', 'openai', 'anthropic', 'machine learning', 'model',
    'agent', 'agents', 'generative', 'automation', 'copilot',
    # Enterprise & digital transformation
    'enterprise', 'digital transformation', 'saas', 'platform', 'integration',
    'workflow', 'productivity', 'adoption',
    # SMB / business
    'smb', 'small business', 'mid-market', 'founder', 'startup', 'growth', 'strategy',
    # E-commerce / retail
    'ecommerce', 'e-commerce', 'retail', 'conversion', 'shopify', 'marketplace',
    # Cybersecurity
    'security', 'cyber', 'breach', 'vulnerability', 'malware', 'ransomware', 'zero-day',
    'threat', 'cve', 'phishing', 'attack', 'infosec', 'apt',
    # Cloud / DevOps / infrastructure
    'cloud', 'aws', 'azure', 'gcp', 'devops', 'infrastructure', 'kubernetes', 'docker',
    # Analytics / forecasting / operations
    'analytics', 'forecast', 'data', 'insight', 'operations', 'lean', 'efficiency',
    # Marketing
    'marketing', 'seo', 'content', 'social media', 'brand', 'campaign',
]

# Newsletter type weights — higher means more likely to be relevant to Zimplixio
NEWSLETTER_WEIGHTS = {
    'TLDR AI': 10,
    'TLDR InfoSec': 8,
    'TLDR IT': 7,
    'TLDR Founders': 7,
    'TLDR DevOps': 6,
    'TLDR Marketing': 6,
    'TLDR': 5,
    'TLDR Dev': 4,
    'DragonNews Bytes': 7,
}

# Signals with no actionable SMB opportunity — macro finance, politics, pure dev tutorials
NEGATIVE_KEYWORDS = [
    # Pure macro/financial news — no SMB action
    'misses targets', 'missed targets', 'revenue shortfall', 'stock fell', 'shares fell',
    'trade wobbles', 'renegotiate', 'deal blocked', 'testifies', 'lawsuit',
    # Pure developer/language tutorials with no business angle
    'scroll-driven animations', 'css animation', 'animation-timeline',
    'javascript tutorial', 'legal ownership over ai code',
    # Arrests and crime stories — no SMB opportunity
    'extradites', 'teenager', 'double life', 'taunted fbi', 'high-flying',
]

# Signals that strongly indicate an SMB business opportunity get a bonus
OPPORTUNITY_KEYWORDS = [
    # New tools/capabilities becoming accessible
    'launch', 'launches', 'released', 'now available', 'new tool', 'new feature',
    'open source', 'free', 'affordable', 'small business',
    # Adoption and implementation signals
    'adopt', 'adoption', 'deploy', 'automate', 'workflow', 'integration',
    'save time', 'reduce cost', 'increase revenue', 'grow',
    # Practical tech SMBs can use
    'e-commerce', 'ecommerce', 'marketing', 'customer', 'sales', 'forecast',
    'inventory', 'support', 'checkout', 'recommendation',
]


def score_email(email: dict) -> int:
    """Return a relevance score for an email. Higher = more relevant."""
    subject = (email.get('subject') or '').lower()
    snippet = (email.get('snippet') or '').lower()
    excerpt = (email.get('excerpt') or '').lower()
    text = f"{subject} {snippet} {excerpt}"

    score = 0

    # Newsletter type base weight
    newsletter = email.get('newsletter', '')
    score += NEWSLETTER_WEIGHTS.get(newsletter, 3)

    # Positive keyword matches (each unique keyword = +2)
    matched = set()
    for kw in TOPIC_KEYWORDS:
        if kw in text and kw not in matched:
            score += 2
            matched.add(kw)

    # Negative keyword penalty — signals with no SMB opportunity
    for kw in NEGATIVE_KEYWORDS:
        if kw in text:
            score -= 8

    # Opportunity keyword bonus — signals where an SMB can act
    for kw in OPPORTUNITY_KEYWORDS:
        if kw in text:
            score += 3

    # DNB emails with structured excerpts get a bonus for richness
    if email.get('type') == 'dnb' and email.get('excerpt'):
        score += 3

    return score


def main():
    if not os.path.exists(INPUT_FILE):
        print(f"ERROR: {INPUT_FILE} not found. Run emails_parse.py first.")
        return

    with open(INPUT_FILE, 'r') as f:
        emails = json.load(f)

    if not isinstance(emails, list):
        print(f"ERROR: Expected a list in {INPUT_FILE}.")
        return

    # Score all emails
    scored = []
    for email in emails:
        s = score_email(email)
        scored.append({**email, '_relevance_score': s})

    # Sort by score descending, take top N
    scored.sort(key=lambda e: e['_relevance_score'], reverse=True)
    top = scored[:TOP_N]

    os.makedirs('tmp', exist_ok=True)
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(top, f, indent=2, ensure_ascii=False)

    print(f"Done. {len(top)} stories selected from {len(emails)} emails. Output: {OUTPUT_FILE}")
    for e in top:
        print(f"  [{e['_relevance_score']:>3}] {e.get('newsletter','?')} — {e.get('subject','?')[:70]}")


if __name__ == '__main__':
    main()
