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

_env = dotenv_values(os.path.join(os.path.dirname(__file__), '..', '.env'))
os.environ.update({k: v for k, v in _env.items() if v})

INPUT_FILE = 'tmp/emails_filtered.json'
CONTEXT_FILE = 'tmp/market_context.json'
OUTPUT_FILE = 'tmp/posts_draft.json'

# Rotating Tavily queries for market research posts
TAVILY_RESEARCH_QUERIES = [
    'small business AI automation productivity gains 2025',
    'SMB data management workflow efficiency statistics',
    'small business technology adoption challenges USA 2025',
    'SMB ERP integration benefits operational visibility',
    'agentic AI small business use cases ROI',
    'small business manual process automation cost savings',
    'SMB cloud migration benefits growing business',
    'small business digital transformation success stories 2025',
]

OUTCOME_PATTERNS = [
    {
        'type': 'Spreadsheet → system',
        'angle': 'A business running entirely on spreadsheets. One wrong formula away from a crisis. We built them a custom app backed by a real database. Nothing changed about the business — everything changed about how it operated.',
        'trigger_keywords': ['manual', 'spreadsheet', 'data', 'process', 'error', 'scaling'],
    },
    {
        'type': 'Desktop → SaaS',
        'angle': 'A client had a working desktop app. It worked, but it could not scale, could not be accessed remotely, and could not grow. We rebuilt it as a SaaS product. Same core logic — completely different business model and growth ceiling.',
        'trigger_keywords': ['software', 'product', 'modernization', 'saas', 'desktop', 'scale'],
    },
    {
        'type': 'Failed project rescue',
        'angle': 'The previous contractor walked away. Critical data sat incomplete and unusable. We came in, finished the job, and got the business moving again. This is an underused angle — it signals credibility and technical depth without sounding salesy.',
        'trigger_keywords': ['contractor', 'debt', 'incomplete', 'failed', 'rescue', 'trust'],
    },
    {
        'type': 'ERP integration',
        'angle': 'ERPs are islands. Data sits inside them but cannot get out in a useful form. We connect them — to each other, to custom apps, to reporting layers — so the business can finally see what is actually happening.',
        'trigger_keywords': ['erp', 'silo', 'reporting', 'data', 'integration', 'visibility'],
    },
    {
        'type': 'Agentic automation',
        'angle': 'A human being was the bridge between systems. Extract data, move it, trigger the next step, send the notification, update the record. Every day. Manually. An agent does it instead. The human sets the rules once.',
        'trigger_keywords': ['ai', 'agent', 'automation', 'workflow', 'productivity', 'headcount'],
    },
    {
        'type': 'Custom reporting',
        'angle': 'The business was making decisions on gut feelings and incomplete information. We built a reporting layer on top of their live data. Now they know what is actually happening — before it becomes a problem.',
        'trigger_keywords': ['reporting', 'decision', 'forecast', 'analytics', 'data', 'visibility'],
    },
]

SYSTEM_PROMPT = """You write LinkedIn posts for Zimplixio. Zimplixio helps small and medium businesses run better using technology — AI tools, custom software, data pipelines, ERP integrations, and agentic workflows.

The audience is owners and managers at companies with 5 to 200 employees. Busy, practical people who care about saving time, cutting costs, and growing. They are not technical. They do not follow tech news.

--- STRUCTURE ---

HOOK (lines 1–2):
The hook must work before LinkedIn's "see more" cut-off — first 1 to 2 short lines. Max 1 sentence per line.
Rotate through these formulas:
  - Confession: "I spent X years doing [thing] wrong."
  - Pattern interrupt: "Nobody talks about the hardest part of [topic]."
  - Provocation: a short contrarian take that stops the scroll.
  - List tease: "3 things I wish I knew before [milestone]."
  - Story promise: "We [achieved result]. Here's exactly how."
  - Bold statement: a direct claim about an opportunity.
  - Question: a thought-provoking question.
Never open with "I'm excited to share", "Did you know", or any weak filler line.

[blank line]

BODY (3 to 5 short paragraphs):
Use 1 to 2 sentences per paragraph — never more. One idea per line. Blank line between each paragraph.
Alternate between narrative and bullet formats (✓ or → markers).
Keep it concrete. Advisor tone, not consultant tone.

[blank line]

CTA (1 line):
No URL in the post body — links go in the first comment.
Format: "If you want [specific outcome], book a free call — link in the first comment 👇"

--- FORMATTING RULES ---
- Every section separated by a blank line.
- 1 to 2 emojis max as visual anchors, not decoration.
- Special characters allowed: → ✓ |
- No hashtags. No URLs in the post body.
- Total length: 120 to 150 words.

--- VOICE RULES ---
- Plain language. 8th grade reading level. Write like you talk.
- Forbidden: leverage, ecosystem, paradigm, synergy, enterprise-grade, cutting-edge, navigate, landscape, seamless, robust, empower, revolutionize, transform, game-changer, unlock, harness, elevate.
- Positive and opportunity-focused. No fear, no warnings, no doom.

--- ZIMPLIXIO OUTCOME PATTERNS ---
| Outcome | Post angle |
|---|---|
| Spreadsheet → system | Business on spreadsheets gets a custom app + real database. Nothing changed about the business — everything changed about how it operated. |
| Desktop → SaaS | Working desktop app rebuilt as SaaS. Same logic — different business model and growth ceiling. |
| Failed project rescue | Previous contractor walked away. We finished the job. Signals credibility without sounding salesy. |
| ERP integration | ERPs are islands. We connect them so the business can see what's actually happening. |
| Agentic automation | Human was the bridge between systems. Agent does it instead. Rules set once. |
| Custom reporting | Stopped making gut decisions. Started working from live data they trust. |

--- ZIMPLIXIO PROOF LOOP ---
When topic is AI/automation/agentic: Zimplixio built its own content agent — monitors SMB trends, matches to services, proposes posts daily. Every post is proof agentic workflows work for small businesses.
Angle: "We built ourselves an agent that monitors SMB trends and proposes LinkedIn posts every morning. Research done, hook written, data sourced. This is what we build for clients." """


def load_market_context() -> list:
    if not os.path.exists(CONTEXT_FILE):
        return []
    try:
        with open(CONTEXT_FILE, 'r') as f:
            data = json.load(f)
        return data.get('insights', [])
    except Exception:
        return []


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


def pick_outcome_pattern(recent_signals: list) -> dict:
    """Let the agent pick the best outcome pattern based on recent content."""
    signal_text = ' '.join(recent_signals).lower()
    scored = []
    for pattern in OUTCOME_PATTERNS:
        score = sum(1 for kw in pattern['trigger_keywords'] if kw in signal_text)
        scored.append((score, random.random(), pattern))
    scored.sort(key=lambda x: (-x[0], x[1]))
    return scored[0][2]


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


def generate(client: anthropic.Anthropic, prompt: str) -> str:
    message = client.messages.create(
        model='claude-sonnet-4-6',
        max_tokens=600,
        system=SYSTEM_PROMPT,
        messages=[{'role': 'user', 'content': prompt}]
    )
    return message.content[0].text.strip()


def slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_-]+', '-', text)
    return text[:50].strip('-')


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

    market_insights = load_market_context()
    print(f"  Loaded {len(market_insights)} market insights")

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
            post_text = generate(client, build_prompt_email(email, insight))
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
        run_count = len(drafts)
        for i in range(2):
            query_idx = (run_count + i) % len(TAVILY_RESEARCH_QUERIES)
            query = TAVILY_RESEARCH_QUERIES[query_idx]
            print(f"  [research] {query[:60]}")
            try:
                response = tavily.search(query=query, search_depth='advanced', max_results=4)
                results = response.get('results', [])
                insight = pick_relevant_insight(market_insights, query.lower(), used_insight_indices)
                post_text = generate(client, build_prompt_research(query, results, insight))
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
    recent_signals = [d.get('source_subject', '') for d in drafts]
    pattern = pick_outcome_pattern(recent_signals)
    print(f"  [owned] Outcome pattern: {pattern['type']}")
    try:
        insight = pick_relevant_insight(market_insights, pattern['type'].lower(), used_insight_indices)
        post_text = generate(client, build_prompt_owned(pattern, insight))
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

    print(f"\nDone. {len(drafts)} posts generated ({len(errors)} errors). Output: {OUTPUT_FILE}")


if __name__ == '__main__':
    main()
