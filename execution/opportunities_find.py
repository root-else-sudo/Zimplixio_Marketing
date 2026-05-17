# opportunities_find.py
# Finds 5 concrete, actionable business opportunities for Zimplixio using Tavily + Claude.
# Each opportunity targets a specific SMB sector with 5 action items to start getting clients.
# Input:  none (searches live)
# Output: tmp/opportunities.json (5 opportunity objects)

import json
import os
from datetime import datetime
from dotenv import dotenv_values
import anthropic
from tavily import TavilyClient

_env = dotenv_values(os.path.join(os.path.dirname(__file__), '..', '.env'))
os.environ.update({k: v for k, v in _env.items() if v})

OUTPUT_FILE = 'tmp/opportunities.json'

# One targeted search per sector — concrete pain points, not generic AI trends
SECTOR_QUERIES = [
    {
        'sector': 'Professional Services',
        'query': 'law firm accounting consultancy manual billing time tracking inefficiency small business 2025',
    },
    {
        'sector': 'Construction & Trades',
        'query': 'small construction company project management scheduling software gap problems 2025',
    },
    {
        'sector': 'Healthcare & Wellness',
        'query': 'small clinic private practice administrative burden scheduling billing technology 2025',
    },
    {
        'sector': 'Retail & E-commerce',
        'query': 'small retailer inventory management multi-channel selling manual process pain points 2025',
    },
    {
        'sector': 'Logistics & Distribution',
        'query': 'small logistics company dispatch route tracking manual spreadsheet problems 2025',
    },
]

SYSTEM_PROMPT = """You are a business development strategist for Zimplixio, a technology firm that helps SMBs implement AI-powered automation, system integrations, and custom software solutions.

Given Tavily search results about SMB pain points in a specific sector, extract ONE very specific, actionable business opportunity for Zimplixio to pursue RIGHT NOW.

Return a JSON object with these exact fields:
{
  "title": "Short opportunity title (under 10 words, specific)",
  "sector": "The sector/industry",
  "signal": "One sentence citing a specific stat, trend, or problem from the search results. Be concrete — include numbers if available.",
  "zimplixio_angle": "Exactly how Zimplixio solves this — which specific service (automation, integration, custom software, AI agent) and what the outcome looks like.",
  "actions": [
    "Action 1: Specific outreach or tactic to land the first client in this sector",
    "Action 2: ...",
    "Action 3: ...",
    "Action 4: ...",
    "Action 5: ..."
  ]
}

Rules:
- Be brutally specific. No vague language like "leverage technology" or "implement solutions".
- The 5 actions must be executable this week — real steps like "Call 10 local law firms and ask if they track billable hours in Excel", not "build brand awareness".
- The signal must cite something from the search results, not generic knowledge.
- The zimplixio_angle must name a concrete deliverable (e.g. "automated invoice-to-payment workflow", "Slack-to-CRM integration", "AI dispatch routing agent").
"""


def find_opportunities():
    tavily = TavilyClient(api_key=os.environ['TAVILY_API_KEY'])
    claude = anthropic.Anthropic(api_key=os.environ['ANTHROPIC_API_KEY'])

    opportunities = []

    for item in SECTOR_QUERIES:
        sector = item['sector']
        query = item['query']
        print(f"[opportunities] Searching: {sector}...")

        try:
            results = tavily.search(
                query=query,
                search_depth='advanced',
                max_results=5,
            )

            snippets = []
            for r in results.get('results', []):
                title = r.get('title', '')
                content = r.get('content', '')[:400]
                url = r.get('url', '')
                snippets.append(f"- {title}\n  {content}\n  Source: {url}")

            search_text = '\n\n'.join(snippets)

            user_prompt = f"""Sector: {sector}

Search results:
{search_text}

Find the best single business opportunity for Zimplixio in this sector based on these results. Return only the JSON object, no other text."""

            response = claude.messages.create(
                model='claude-sonnet-4-6',
                max_tokens=800,
                system=SYSTEM_PROMPT,
                messages=[{'role': 'user', 'content': user_prompt}],
            )

            raw = response.content[0].text.strip()

            # Strip markdown code fences if present
            if raw.startswith('```'):
                raw = raw.split('```')[1]
                if raw.startswith('json'):
                    raw = raw[4:]
            raw = raw.strip()

            opp = json.loads(raw)
            opp['generatedAt'] = datetime.now().isoformat()
            opportunities.append(opp)
            print(f"[opportunities] ✓ {sector}: {opp.get('title', '?')}")

        except Exception as e:
            print(f"[opportunities] ✗ {sector} failed: {e}")

    os.makedirs('tmp', exist_ok=True)
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(opportunities, f, indent=2)

    print(f"[opportunities] Saved {len(opportunities)} opportunities to {OUTPUT_FILE}")
    return opportunities


if __name__ == '__main__':
    find_opportunities()
