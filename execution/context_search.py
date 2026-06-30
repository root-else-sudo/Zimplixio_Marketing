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
from utils import r2_storage

_env = dotenv_values(os.path.join(os.path.dirname(__file__), '..', '.env'))
os.environ.update({k: v for k, v in _env.items() if v})

CONTEXT_FILE = 'tmp/market_context.json'

# Rotating search queries — picked round-robin each run
SEARCH_QUERIES = [
    # Industry-specific operational pain
    'trucking logistics small fleet operations technology challenges',
    'HVAC field service company operational management problems statistics',
    'waste management route optimization technology adoption gap',
    'construction company field data management challenges subcontractor',
    'food distribution small business inventory software operational problems',
    'pest control scheduling dispatch software challenges small business',
    'field service company mobile workforce management barriers',
    'service business quoting estimating manual process errors cost',
    'small business developer abandoned incomplete custom software',
    'delivery company driver scheduling dispatch technology problems',
    # Pain statistics with real numbers
    'small business manual processes labor cost productivity statistics',
    'SMB data visibility reporting gap operational decisions statistics',
    'small business payroll time tracking errors cost statistics',
    'field service paper forms digital conversion ROI statistics',
    'small business spreadsheet operational risk statistics report',
    'SMB custom software ROI operational efficiency case study',
    'agentic AI workflow automation small business productivity statistics',
    'small business data pipeline reporting automation benefits ROI',
    'SMB technology adoption barriers talent shortage statistics',
    'small business tech debt operational systems integration cost',
]

ZIMPLIXIO_SERVICES = """
1. Technology Roadmap & Planning — Gap analysis, tech stack evaluation, vendor selection, 90-day execution roadmap.
2. Solution Architecture & Implementation — Custom software, system integrations (CRM/ERP/APIs), cloud architecture and migration.
3. Data Engineering & Automation — Workflow automation, data pipelines, analytics and reporting. Replaces manual processes.
4. Embedded Technical Partnership — Ongoing technical leadership, managed hosting, maintenance of existing systems.
5. AI & Agentic Automation — AI readiness assessment, agentic workflow design, responsible AI adoption, team enablement.
"""


def load_context() -> dict:
    return r2_storage.get_json(
        'market_context.json',
        local_fallback=CONTEXT_FILE,
        default={'last_updated': datetime.now().isoformat(), 'sources': [], 'insights': [], 'search_run_count': 0},
    )


def save_context(data: dict):
    r2_storage.put_json('market_context.json', data, local_fallback=CONTEXT_FILE)


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

    prompt = f"""You are extracting SMB market insights for Zimplixio, a technology contractor that helps operationally complex small businesses — trucking, field service, distribution, construction, pest control, and similar industries — replace manual processes with software that works.

Search query that found this content: "{query}"

From the search results below, extract 3-5 specific, credible insights or statistics about: operational pain in small businesses, manual process costs, scheduling and dispatch problems, data visibility gaps, payroll or time-tracking errors, failed software projects, or technology adoption barriers in non-glamorous industries. Prioritize insights with real numbers or percentages. Skip generic AI trend content or corporate enterprise content — focus on small business operational reality.

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
            days=30,
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
