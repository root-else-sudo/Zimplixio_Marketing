# posts_generate.py
# Generates 5 LinkedIn posts per run from 3 blended sources:
#   - 2 email-based (from filtered newsletters)
#   - 2 Tavily market research (pure SMB trend, no email needed)
#   - 1 Zimplixio-owned (outcome pattern, agent picks best fit)
# Enriches all posts with SMB market context from tmp/market_context.json.
# Input:  tmp/emails_filtered.json, tmp/market_context.json
# Output: tmp/posts_draft.json

import json
import os
import re
import random
from datetime import datetime
from dotenv import dotenv_values
import anthropic
from tavily import TavilyClient
from utils import r2_storage

_env = dotenv_values(os.path.join(os.path.dirname(__file__), '..', '.env'))
os.environ.update({k: v for k, v in _env.items() if v})

INPUT_FILE = 'tmp/emails_filtered.json'
CONTEXT_FILE = 'tmp/market_context.json'
OUTPUT_FILE = 'tmp/posts_draft.json'

# Rotating Tavily queries — operational pain by industry, recency enforced via days=14
TAVILY_RESEARCH_QUERIES = [
    'trucking fleet dispatch scheduling software problems small business',
    'HVAC field service company scheduling errors lost jobs revenue',
    'food distribution inventory tracking manual process failures operations',
    'construction subcontractor data management scheduling spreadsheet problems',
    'small business payroll errors manual time tracking cost productivity',
    'pest control field service mobile app adoption challenges',
    'waste management route optimization technology gap small fleet',
    'service company quoting estimating manual pricing errors lost revenue',
    'small business developer abandoned incomplete custom software project',
    'operations director manual reporting disconnected systems data silos',
    'delivery company driver dispatch scheduling technology problems',
    'field service company paper work orders digital transformation barriers',
]

OUTCOME_PATTERNS = [
    {
        'type': 'Dispatch on spreadsheets',
        'angle': 'A delivery or field service business managing schedules on a shared spreadsheet. Someone always overwrites someone else. Jobs go out with errors. Crews show up to the wrong location. They replaced the spreadsheet with a simple dispatch tool. Same team, same routes — no more morning chaos.',
        'trigger_keywords': ['dispatch', 'route', 'schedule', 'driver', 'delivery', 'field', 'crew'],
    },
    {
        'type': 'Paper-based field operations',
        'angle': 'Technicians filling out paper forms in the field. Back at the office, someone types the same data into a system. Errors, delays, lost forms. They went digital — mobile forms, instant sync, no re-entry. The data is in the system before the tech drives back.',
        'trigger_keywords': ['field', 'technician', 'paper', 'form', 'mobile', 'service', 'inspection'],
    },
    {
        'type': 'No reporting visibility',
        'angle': "A business running 50 people with no dashboard. The owner checks in by calling managers. Nobody knows the real numbers until the books close at month end. They built a simple data pipeline connecting three systems into one view. Now the owner sees yesterday's numbers this morning.",
        'trigger_keywords': ['reporting', 'data', 'visibility', 'dashboard', 'numbers', 'analytics'],
    },
    {
        'type': 'Manual payroll and time tracking',
        'angle': 'Employees calling in their hours. A manager writing it down, transferring it to a spreadsheet, sending it to payroll. Every week, the same process. One wrong entry and the check is wrong. They automated the handoff. Timesheets go straight to payroll without anyone touching them in between.',
        'trigger_keywords': ['payroll', 'hours', 'timesheet', 'overtime', 'manual', 'wage', 'labor'],
    },
    {
        'type': 'Disconnected quoting and billing',
        'angle': 'A service business building quotes in Word. Copying from old quotes, changing numbers by hand. When pricing changes, old quotes sit in inboxes uncorrected. They built a quoting tool connected to their actual price list. Quotes go out in minutes and the numbers are always right.',
        'trigger_keywords': ['quote', 'estimate', 'pricing', 'proposal', 'invoice', 'billing', 'contract'],
    },
    {
        'type': 'Failed software project rescue',
        'angle': 'They hired a developer. Paid a deposit. Got a half-built app and then silence. Now they have software nobody can finish and a business problem still unsolved. A new team came in to pick up where the other left off — not to rebuild from scratch, but to finish the job.',
        'trigger_keywords': ['contractor', 'developer', 'incomplete', 'abandoned', 'project', 'rescue', 'debt'],
    },
]

SYSTEM_PROMPT_BASE = """You write LinkedIn posts for Zimplixio, a technology contractor that helps operationally complex small businesses fix the systems that are slowing them down.

The businesses Zimplixio serves run real operations: delivery fleets, field service crews, distribution centers, construction sites, service routes. They cannot attract software engineers. They make decisions on spreadsheets, phone calls, and gut feeling. They know something is broken but do not know it can be fixed.

Zimplixio's three core services:
- AI and agentic automation — replacing manual, repetitive workflows with software that runs on its own
- Data engineering and automation — connecting systems and building dashboards so owners can see what is actually happening in real time
- Custom software and integrations — building apps and connecting tools when off-the-shelf software does not fit the operation

Every post follows this structure:

1. HOOK (1–2 lines): Open with a specific operational pain that a business owner or ops manager would recognize as their exact situation. Lead with the pain, not the industry. No statistics in the hook. No buzzwords. Make them stop scrolling.

2. BODY (3–4 short paragraphs): One idea per paragraph. One to two sentences each. Be concrete — reference real operational details: routes, crews, timesheets, work orders, invoices, quotes, job tickets. Describe what changed without naming Zimplixio or sounding like an ad.

3. OUTCOME (1–2 sentences): What the business can now do that it could not do before. A real capability or relief, not a revenue number.

4. CLOSE (1 line): A question or direct statement that makes the reader feel seen and understood.

Voice rules:
- Short sentences. No sentence longer than 20 words.
- Plain language. Write like you talk to a peer who runs a business.
- Never use: leverage, synergy, scalability, digital transformation, robust, seamless, holistic, revolutionize, game-changer, unlock, harness, elevate, empower, cutting-edge, enterprise-grade, ecosystem, paradigm
- Do not name Zimplixio in the post body
- Do not open with "I" or with a statistic
- No emojis
- No hashtags
- No URLs in the post body
- 150 to 200 words total

The reader is the owner or the operations director of a 20–200 person business in an industry that does not attract software engineers. They feel stuck. They know something is broken. They do not know it can be fixed."""


def load_market_context() -> list:
    return r2_storage.get_json('market_context.json', local_fallback=CONTEXT_FILE, default={'insights': []}).get('insights', [])


def load_context() -> dict:
    return r2_storage.get_json(
        'market_context.json',
        local_fallback=CONTEXT_FILE,
        default={
            'last_updated': '',
            'sources': [],
            'insights': [],
            'search_run_count': 0,
            'tavily_run_count': 0,
            'outcome_pattern_index': 0,
            'recent_hooks': [],
        },
    )


def save_context(data: dict):
    r2_storage.put_json('market_context.json', data, local_fallback=CONTEXT_FILE)


def pick_relevant_insight(insights: list, signal_text: str, used_indices: set) -> dict | None:
    if not insights:
        return None

    topic_keywords = {
        'ai': ['ai', 'artificial intelligence', 'machine learning', 'automation', 'agent', 'llm', 'gpt'],
        'data': ['data', 'analytics', 'reporting', 'pipeline', 'database', 'insight'],
        'workflow': ['workflow', 'process', 'manual', 'efficiency', 'automat', 'operation'],
        'tech': ['technology', 'software', 'tool', 'platform', 'digital', 'cloud', 'integration'],
        'growth': ['growth', 'revenue', 'scale', 'business', 'customer'],
    }

    scored = []
    for i, insight in enumerate(insights):
        if i in used_indices:
            continue
        score = 0
        insight_text = f"{insight.get('topic', '')} {insight.get('stat', '')} {insight.get('zimplixio_service', '')}".lower()
        for keywords in topic_keywords.values():
            signal_match = any(kw in signal_text for kw in keywords)
            insight_match = any(kw in insight_text for kw in keywords)
            if signal_match and insight_match:
                score += 2
            elif insight_match:
                score += 1
        scored.append((score, i, insight))

    if not scored:
        return None

    scored.sort(key=lambda x: (-x[0], random.random()))
    _, best_idx, best_insight = scored[0]
    used_indices.add(best_idx)
    return best_insight


def build_prompt_email(email: dict, insight: dict | None) -> str:
    if email.get('type') == 'dnb':
        title = email.get('article_title', email.get('subject', ''))
        excerpt = email.get('excerpt') or email.get('snippet', '')
        signal = f"Topic: {title}"
        if excerpt and len(excerpt) > 20:
            signal += f"\nContext: {excerpt[:300]}"
    else:
        subject = email.get('subject', '')
        snippet = email.get('snippet', '')
        subject_clean = subject.encode('ascii', 'ignore').decode().strip(' ,')
        signal = f"Topic: {subject_clean}"
        if snippet and len(snippet) > 20:
            signal += f"\nContext: {snippet[:300]}"

    context_block = _format_insight(insight)
    return f"{signal}\n{context_block}\nWrite a Zimplixio LinkedIn post. Use the topic as a market signal — write about the underlying business opportunity for SMB owners."


def build_prompt_research(query: str, search_results: list, insight: dict | None) -> str:
    combined = '\n'.join(
        f"- {r.get('title', '')}: {r.get('content', '')[:200]}"
        for r in search_results[:4]
    )
    context_block = _format_insight(insight)
    return (
        f"Market research topic: {query}\n\n"
        f"Recent findings:\n{combined}\n"
        f"{context_block}\n"
        f"Write a Zimplixio LinkedIn post grounded in this SMB market research. "
        f"Do not summarize the research — use it as a signal to write about a real business opportunity."
    )


def build_prompt_owned(pattern: dict, insight: dict | None) -> str:
    context_block = _format_insight(insight)
    return (
        f"Post type: Zimplixio-owned outcome story\n"
        f"Outcome pattern: {pattern['type']}\n"
        f"Angle to use: {pattern['angle']}\n"
        f"{context_block}\n"
        f"Write a Zimplixio LinkedIn post using this outcome pattern as the foundation. "
        f"Make it feel like a real story, not a case study. First person, specific, credible."
    )


def _format_insight(insight: dict | None) -> str:
    if not insight:
        return ''
    return (
        f"\nMARKET CONTEXT (ground the post in this data):\n"
        f"Stat: {insight['stat']}\n"
        f"Why it matters: {insight['context']}\n"
        f"Zimplixio angle: {insight['zimplixio_service']}\n"
        f"Use as hook or supporting evidence — your choice. Do not cite the source.\n"
    )


def generate(client: anthropic.Anthropic, prompt: str, system: str = SYSTEM_PROMPT_BASE) -> str:
    message = client.messages.create(
        model='claude-sonnet-4-6',
        max_tokens=600,
        system=system,
        messages=[{'role': 'user', 'content': prompt}]
    )
    return message.content[0].text.strip()


def slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_-]+', '-', text)
    return text[:50].strip('-')


def pick_research_query_indices(tavily_run_count: int, num_queries: int) -> list[int]:
    return [(tavily_run_count + i) % num_queries for i in range(2)]


def pick_outcome_pattern_by_index(context: dict) -> dict:
    idx = context.get('outcome_pattern_index', 0)
    pattern = OUTCOME_PATTERNS[idx % len(OUTCOME_PATTERNS)]
    context['outcome_pattern_index'] = idx + 1
    return pattern


def extract_hook(post_text: str) -> str:
    for line in post_text.split('\n'):
        line = line.strip()
        if line:
            return line[:150]
    return ''


def build_system_prompt(recent_hooks: list[str]) -> str:
    if not recent_hooks:
        return SYSTEM_PROMPT_BASE
    hooks_list = '\n'.join(f'- {h}' for h in recent_hooks[-5:])
    return (
        SYSTEM_PROMPT_BASE
        + f'\n\n--- AVOID REPEATING ---\n'
        + f'Do not reuse these opening hooks or angles from recent posts:\n{hooks_list}'
    )


def main():
    api_key = os.getenv('ANTHROPIC_API_KEY')
    tavily_key = os.getenv('TAVILY_API_KEY')
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set")
        return

    emails = []
    if os.path.exists(INPUT_FILE):
        with open(INPUT_FILE, 'r') as f:
            emails = json.load(f)
        if not isinstance(emails, list):
            emails = []

    context = load_context()
    market_insights = context.get('insights', [])
    recent_hooks: list[str] = context.get('recent_hooks', [])
    system_prompt = build_system_prompt(recent_hooks)
    print(f"  Loaded {len(market_insights)} market insights, {len(recent_hooks)} recent hooks")

    client = anthropic.Anthropic(api_key=api_key)
    tavily = TavilyClient(api_key=tavily_key) if tavily_key else None

    drafts = []
    errors = []
    used_insight_indices: set = set()
    today = datetime.now().strftime('%Y-%m-%d')

    # ── Source 1: Email-based posts (up to 2) ─────────────────────────────────
    for email in emails[:2]:
        subject = email.get('article_title') or email.get('subject', '')
        newsletter = email.get('newsletter', 'unknown')
        signal_text = f"{subject} {email.get('excerpt') or email.get('snippet', '')}".lower()
        insight = pick_relevant_insight(market_insights, signal_text, used_insight_indices)

        print(f"  [email] {newsletter} — {subject[:50]}")
        try:
            post_text = generate(client, build_prompt_email(email, insight), system_prompt)
            recent_hooks.append(extract_hook(post_text))
            drafts.append({
                'source_type': 'email',
                'newsletter': newsletter,
                'source_subject': subject,
                'source_date': email.get('date', today),
                'slug': slugify(subject),
                'post': post_text,
            })
            print(f"    Done ({len(post_text)} chars)")
        except Exception as e:
            errors.append({'source': subject, 'error': str(e)})
            print(f"    WARN: {e}")

    # ── Source 2: Tavily market research posts (2) ────────────────────────────
    if tavily:
        tavily_run_count = context.get('tavily_run_count', 0)
        query_indices = pick_research_query_indices(tavily_run_count, len(TAVILY_RESEARCH_QUERIES))
        context['tavily_run_count'] = tavily_run_count + 2
        for query_idx in query_indices:
            query = TAVILY_RESEARCH_QUERIES[query_idx]
            print(f"  [research] {query[:60]}")
            try:
                response = tavily.search(query=query, search_depth='advanced', max_results=4, days=14)
                results = response.get('results', [])
                insight = pick_relevant_insight(market_insights, query.lower(), used_insight_indices)
                post_text = generate(client, build_prompt_research(query, results, insight), system_prompt)
                recent_hooks.append(extract_hook(post_text))
                drafts.append({
                    'source_type': 'research',
                    'newsletter': 'Market Research',
                    'source_subject': query,
                    'source_date': today,
                    'slug': slugify(query),
                    'post': post_text,
                })
                print(f"    Done ({len(post_text)} chars)")
            except Exception as e:
                errors.append({'source': query, 'error': str(e)})
                print(f"    WARN: {e}")
    else:
        print("  [research] Skipped — TAVILY_API_KEY not set")

    # ── Source 3: Zimplixio-owned outcome post (1) ────────────────────────────
    pattern = pick_outcome_pattern_by_index(context)
    print(f"  [owned] Outcome pattern: {pattern['type']}")
    try:
        insight = pick_relevant_insight(market_insights, pattern['type'].lower(), used_insight_indices)
        post_text = generate(client, build_prompt_owned(pattern, insight), system_prompt)
        recent_hooks.append(extract_hook(post_text))
        drafts.append({
            'source_type': 'owned',
            'newsletter': 'Zimplixio',
            'source_subject': pattern['type'],
            'source_date': today,
            'slug': slugify(pattern['type']),
            'post': post_text,
        })
        print(f"    Done ({len(post_text)} chars)")
    except Exception as e:
        errors.append({'source': pattern['type'], 'error': str(e)})
        print(f"    WARN: {e}")

    os.makedirs('tmp', exist_ok=True)
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(drafts, f, indent=2, ensure_ascii=False)

    context['recent_hooks'] = recent_hooks[-10:]
    save_context(context)
    print(f"\nDone. {len(drafts)} posts generated ({len(errors)} errors). Output: {OUTPUT_FILE}")


if __name__ == '__main__':
    main()
