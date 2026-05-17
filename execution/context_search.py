# context_search.py
# Searches for fresh SMB market insights using Tavily on every pipeline run.
# Rotates through search queries to avoid repetition over time.
# Appends new insights to tmp/market_context.json.
# Input:  tmp/market_context.json
# Output: tmp/market_context.json (updated)

import json
import os
import re
from datetime import datetime
from dotenv import dotenv_values
import anthropic
from tavily import TavilyClient

_env = dotenv_values(os.path.join(os.path.dirname(__file__), '..', '.env'))
os.environ.update({k: v for k, v in _env.items() if v})

CONTEXT_FILE = 'tmp/market_context.json'

# Rotating search queries — picked round-robin each run
SEARCH_QUERIES = [
    'SMB small business AI automation adoption statistics 2025',
    'small business technology investment trends USA 2025',
    'SMB data management challenges statistics report',
    'small business workflow automation ROI results',
    'SMB AI readiness gap enterprise vs small business 2025',
    'small business manual processes cost productivity loss',
    'SMB cloud migration benefits statistics',
    'small business digital transformation challenges 2025',
    'AI agents agentic automation small business use cases',
    'SMB data quality revenue impact statistics',
    'small business technology overwhelm adoption barriers',
    'SMB custom software ERP integration benefits ROI',
    'Federal Reserve small business credit survey operational challenges 2025',
    'SBA small business AI technology adoption trends 2025',
    'HubSpot small business sales marketing technology report 2025',
    'small business cash flow operational pressure technology report',
    'SMB spreadsheet manual data errors cost productivity',
    'small business SaaS adoption growth statistics USA',
    'agentic AI workflow automation small business productivity gains',
    'SMB tech debt incomplete software projects contractor failure',
]

ZIMPLIXIO_SERVICES = """
1. Technology Roadmap & Planning — Gap analysis, tech stack evaluation, vendor selection, 90-day execution roadmap.
2. Solution Architecture & Implementation — Custom software, system integrations (CRM/ERP/APIs), cloud architecture and migration.
3. Data Engineering & Automation — Workflow automation, data pipelines, analytics and reporting. Replaces manual processes.
4. Embedded Technical Partnership — Ongoing technical leadership, managed hosting, maintenance of existing systems.
5. AI & Agentic Automation — AI readiness assessment, agentic workflow design, responsible AI adoption, team enablement.
"""


def load_context() -> dict:
    if not os.path.exists(CONTEXT_FILE):
        return {'last_updated': datetime.now().isoformat(), 'sources': [], 'insights': [], 'search_run_count': 0}
    with open(CONTEXT_FILE, 'r') as f:
        return json.load(f)


def save_context(data: dict):
    with open(CONTEXT_FILE, 'w') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def extract_insights(client: anthropic.Anthropic, search_results: list, query: str) -> list:
    """Use Claude to extract structured insights from Tavily search results."""
    if not search_results:
        return []

    # Combine result content into a single block
    combined = ''
    for r in search_results:
        title = r.get('title', '')
        content = r.get('content', '')
        url = r.get('url', '')
        combined += f"\nSource: {title} ({url})\n{content}\n"

    combined = combined[:6000]

    prompt = f"""You are extracting SMB market insights for Zimplixio, a technology services company for small and medium businesses in the USA.

Search query that found this content: "{query}"

From the search results below, extract 3-5 specific, credible insights or statistics about SMB challenges, technology adoption, AI use, automation, data management, or operational efficiency. Prioritize insights with real numbers or percentages. Skip vague or purely promotional content.

For each insight, identify which Zimplixio service it is most relevant to:
{ZIMPLIXIO_SERVICES}

Search results:
\"\"\"
{combined}
\"\"\"

Return a JSON array. Each item must have:
- "stat": the specific stat or insight (1-2 sentences, include numbers if available)
- "context": why this matters for SMB owners (1 sentence)
- "source": publication name and year if visible
- "topic": 2-4 word topic label
- "zimplixio_service": the most relevant Zimplixio service name

Return only valid JSON. No explanation."""

    try:
        message = client.messages.create(
            model='claude-sonnet-4-6',
            max_tokens=800,
            messages=[{'role': 'user', 'content': prompt}]
        )
        raw = message.content[0].text.strip()
        match = re.search(r'\[[\s\S]*\]', raw)
        return json.loads(match.group(0)) if match else []
    except Exception as e:
        print(f"    WARN: Insight extraction failed: {e}")
        return []


def main():
    tavily_key = os.getenv('TAVILY_API_KEY')
    anthropic_key = os.getenv('ANTHROPIC_API_KEY')

    if not tavily_key:
        print("ERROR: TAVILY_API_KEY not set in .env")
        return
    if not anthropic_key:
        print("ERROR: ANTHROPIC_API_KEY not set in .env")
        return

    tavily = TavilyClient(api_key=tavily_key)
    claude = anthropic.Anthropic(api_key=anthropic_key)

    context = load_context()
    run_count = context.get('search_run_count', 0)

    # Pick next query round-robin
    query = SEARCH_QUERIES[run_count % len(SEARCH_QUERIES)]
    print(f"Searching: \"{query}\"")

    try:
        response = tavily.search(
            query=query,
            search_depth='advanced',
            max_results=5,
            include_answer=False,
        )
        results = response.get('results', [])
        print(f"  Found {len(results)} results")
    except Exception as e:
        print(f"  ERROR: Tavily search failed: {e}")
        context['search_run_count'] = run_count + 1
        save_context(context)
        return

    new_insights = extract_insights(claude, results, query)

    if new_insights:
        context['insights'].extend(new_insights)
        context['sources'].append(f"Tavily search: \"{query}\" [{datetime.now().strftime('%Y-%m-%d')}]")
        print(f"  Added {len(new_insights)} fresh insights")
    else:
        print(f"  No usable insights extracted")

    context['search_run_count'] = run_count + 1
    context['last_updated'] = datetime.now().isoformat()
    save_context(context)

    print(f"\nDone. Total insights in context: {len(context['insights'])}")


if __name__ == '__main__':
    main()
