# context_fetch.py
# Fetches SMB market context from fixed sources (PDF + URLs).
# Extracts stats and insights, maps them to Zimplixio services.
# Caches output in tmp/market_context.json. Refreshes weekly.
# Input:  PDF + fixed URLs
# Output: tmp/market_context.json

import json
import os
import time
import requests
from datetime import datetime, timedelta
from dotenv import dotenv_values
import anthropic
from utils import r2_storage

_env = dotenv_values(os.path.join(os.path.dirname(__file__), '..', '.env'))
os.environ.update({k: v for k, v in _env.items() if v})

OUTPUT_FILE = 'tmp/market_context.json'
CACHE_DAYS = 7

PDF_PATH = os.environ.get('PDF_REPORT_PATH', os.path.expanduser('~/Desktop/smb-trends-report-6th-edition_Salesforce.pdf'))

FIXED_URLS = [
    'https://www.salesforce.com/news/stories/smbs-agentic-ai-results/',
    'https://www.salesforce.com/ap/blog/ai-and-the-future-of-small-business/',
    'https://aws.amazon.com/smart-business/resources-for-smb/how-smbs-are-driving-growth-with-ai-5-key-aws-insights/',
]

# Zimplixio service definitions for insight mapping
ZIMPLIXIO_SERVICES = """
1. Technology Roadmap & Planning — Gap analysis, tech stack evaluation, vendor selection, 90-day execution roadmap. For businesses with scattered tools, undocumented workflows, siloed data.
2. Solution Architecture & Implementation — Custom software development, CRM/ERP/API integrations, cloud architecture and migration. End-to-end build and deploy.
3. Data Engineering & Automation — Workflow automation, data pipelines, Azure Data Factory/SSIS, analytics and reporting. Replaces manual entry, approval waits, and re-keying data.
4. Embedded Technical Partnership — Ongoing technical leadership, managed hosting (99.9% uptime), maintenance and evolution of existing systems.
5. AI & Agentic Automation — AI readiness assessment, agentic workflow design, responsible AI adoption framework, team enablement.
"""

# Pre-loaded insights from Salesforce SMB Trends Report 6th Edition (2024)
PRELOADED_INSIGHTS = [
    {
        "stat": "90% of SMBs using AI report more efficient operations",
        "context": "SMBs that have implemented AI are seeing clear returns in productivity and operational efficiency",
        "source": "Salesforce SMB Trends Report, 6th Edition (2024)",
        "topic": "AI adoption ROI",
        "zimplixio_service": "AI & Agentic Automation"
    },
    {
        "stat": "76% of SMBs spend more on technology now than they did last year",
        "context": "Tech investment is accelerating across SMBs as they race to keep up with larger competitors",
        "source": "Salesforce SMB Trends Report, 6th Edition (2024)",
        "topic": "technology investment",
        "zimplixio_service": "Technology Roadmap & Planning"
    },
    {
        "stat": "66% of SMBs are increasing their investment in data management",
        "context": "SMBs recognize that data quality is the foundation of both AI performance and business decisions",
        "source": "Salesforce SMB Trends Report, 6th Edition (2024)",
        "topic": "data management",
        "zimplixio_service": "Data Engineering & Automation"
    },
    {
        "stat": "80% of SMB leaders say improving data quality would increase revenue",
        "context": "Clean, connected data is directly tied to revenue growth — not just operational efficiency",
        "source": "Salesforce SMB Trends Report, 6th Edition (2024)",
        "topic": "data quality and revenue",
        "zimplixio_service": "Data Engineering & Automation"
    },
    {
        "stat": "51% of SMB leaders worry their company will fall behind on technology",
        "context": "Despite optimism, over half of SMB owners feel the pressure of the technology gap widening",
        "source": "Salesforce SMB Trends Report, 6th Edition (2024)",
        "topic": "technology anxiety and readiness",
        "zimplixio_service": "Technology Roadmap & Planning"
    },
    {
        "stat": "47% of SMB leaders feel overwhelmed by the pace of technological change",
        "context": "The speed of AI and automation advancement is leaving many SMB owners unsure where to start",
        "source": "Salesforce SMB Trends Report, 6th Edition (2024)",
        "topic": "technology overwhelm",
        "zimplixio_service": "AI & Agentic Automation"
    },
    {
        "stat": "Only 47% of SMBs describe themselves as 'very data-driven'",
        "context": "Most SMBs collect data but struggle to turn it into decisions — the gap is resources and expertise, not intention",
        "source": "Salesforce SMB Trends Report, 6th Edition (2024)",
        "topic": "data-driven operations",
        "zimplixio_service": "Data Engineering & Automation"
    },
    {
        "stat": "82% of SMB leaders with AI say it will restructure how they operate",
        "context": "AI adoption isn't a small adjustment — leaders implementing it expect it to change how their entire business runs",
        "source": "Salesforce SMB Trends Report, 6th Edition (2024)",
        "topic": "AI transformation",
        "zimplixio_service": "AI & Agentic Automation"
    },
    {
        "stat": "Growing SMBs prioritize improving customer experience and upgrading tech — not just acquiring new customers",
        "context": "The businesses gaining revenue focus on operational foundations, while stagnant ones chase new customers",
        "source": "Salesforce SMB Trends Report, 6th Edition (2024)",
        "topic": "growth strategy",
        "zimplixio_service": "Technology Roadmap & Planning"
    },
    {
        "stat": "85% of SMB IT professionals say AI outputs are only as good as their data inputs",
        "context": "Clean data infrastructure is the prerequisite for any AI investment to deliver real results",
        "source": "Salesforce SMB Trends Report, 6th Edition (2024)",
        "topic": "data quality for AI",
        "zimplixio_service": "Data Engineering & Automation"
    },
]


def is_cache_fresh() -> bool:
    data = r2_storage.get_json('market_context.json', local_fallback=OUTPUT_FILE)
    if not data:
        return False
    try:
        last_updated = datetime.fromisoformat(data.get('last_updated', '2000-01-01'))
        return datetime.now() - last_updated < timedelta(days=CACHE_DAYS)
    except Exception:
        return False


def fetch_url_text(url: str) -> str:
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (compatible; Zimplixio/1.0)'}
        res = requests.get(url, headers=headers, timeout=15)
        res.raise_for_status()
        # Strip HTML tags simply
        import re
        text = re.sub(r'<[^>]+>', ' ', res.text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text[:6000]
    except Exception as e:
        print(f"    WARN: Could not fetch {url}: {e}")
        return ''


def extract_insights_from_text(client: anthropic.Anthropic, text: str, source_label: str) -> list:
    if not text or len(text) < 200:
        return []

    prompt = f"""You are extracting SMB market insights for Zimplixio, a technology services company for small and medium businesses.

From the text below, extract 3-5 specific, data-backed insights or statistics about SMB challenges, technology adoption, AI use, automation, data management, or operational efficiency. Focus on the US market where possible.

For each insight, identify which Zimplixio service it is most relevant to:
{ZIMPLIXIO_SERVICES}

Source text:
\"\"\"
{text}
\"\"\"

Return a JSON array. Each item must have:
- "stat": the specific stat or insight (1-2 sentences, include numbers if available)
- "context": why this matters for SMB owners (1 sentence)
- "source": "{source_label}"
- "topic": 2-4 word topic label
- "zimplixio_service": the most relevant Zimplixio service name

Return only valid JSON. No explanation."""

    try:
        message = client.messages.create(
            model='claude-sonnet-4-6',
            max_tokens=1000,
            messages=[{'role': 'user', 'content': prompt}]
        )
        raw = message.content[0].text.strip()
        import re
        match = re.search(r'\[[\s\S]*\]', raw)
        return json.loads(match.group(0)) if match else []
    except Exception as e:
        print(f"    WARN: Failed to extract insights from {source_label}: {e}")
        return []


def main():
    if is_cache_fresh():
        print("Market context is up to date (< 7 days old). Skipping fetch.")
        return

    print("Fetching market context from fixed sources...")
    api_key = os.getenv('ANTHROPIC_API_KEY')
    client = anthropic.Anthropic(api_key=api_key)

    all_insights = list(PRELOADED_INSIGHTS)
    sources_fetched = ['Salesforce SMB Trends Report, 6th Edition (2024) [pre-loaded]']

    for url in FIXED_URLS:
        print(f"  Fetching: {url[:60]}...")
        text = fetch_url_text(url)
        if text:
            label = url.split('//')[-1].split('/')[0]
            new_insights = extract_insights_from_text(client, text, f"{label} article")
            all_insights.extend(new_insights)
            sources_fetched.append(url)
            print(f"    Extracted {len(new_insights)} insights")
        time.sleep(1)

    os.makedirs('tmp', exist_ok=True)
    output = {
        'last_updated': datetime.now().isoformat(),
        'sources': sources_fetched,
        'insights': all_insights,
    }

    r2_storage.put_json('market_context.json', output, local_fallback=OUTPUT_FILE)

    print(f"\nDone. {len(all_insights)} total insights saved to {OUTPUT_FILE}")


if __name__ == '__main__':
    main()
