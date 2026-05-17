# Directive: Email to LinkedIn Posts

## Goal
Turn daily newsletter emails from authorized senders into LinkedIn post drafts
for Zimplixio. Each post is a Zimplixio marketing asset — opportunity-framed,
plain language, ready for human review and approval before publishing.

## Inputs
- Emails from authorized senders in Gmail:
  - `dan@tldrnewsletter.com` (TLDR newsletters)
  - `noreply@cymru.com` (DragonNews Bytes)

## Steps

1. **Fetch** — Run `execution/emails_fetch.py`
   Pulls recent emails from authorized senders. Outputs `tmp/emails_raw.json`.

2. **Parse** — Run `execution/emails_parse.py`
   Normalizes raw emails into structured data. Warns if `emails_raw.json` is
   older than 24 hours — re-run fetch if so. Outputs `tmp/emails_parsed.json`.

3. **Filter** — Run `execution/emails_filter.py`
   Scores emails for SMB opportunity relevance. Drops macro finance, arrest
   stories, and pure dev tutorials. Keeps top 5. Outputs `tmp/emails_filtered.json`.

4. **Fetch context** — Run `execution/context_fetch.py`
   Extracts SMB market insights from a fixed PDF report and curated URLs.
   Results are cached for 7 days. Outputs/updates `tmp/market_context.json`.

5. **Search context** — Run `execution/context_search.py`
   Runs a rotating Tavily search query on every pipeline run to append fresh
   SMB market insights. Appends to `tmp/market_context.json`.

6. **Generate** — Run `execution/posts_generate.py`
   Calls Claude API to write one LinkedIn post per filtered story, grounded
   in the market context from steps 4–5. Outputs `tmp/posts_draft.json`.

7. **Save** — Run `execution/posts_save.py`
   Saves each post as an individual `.md` file to `posts/YYYY-MM/YYYY-MM-DD/`.

8. **Organize inbox** — Run `execution/emails_organize.py`
   Marks processed emails as read and moves them to the correct Gmail label:
   - TLDR emails → `Education/TLDR`
   - Cymru emails → `Dragron CyberSecurity`

## Outputs
- `.md` draft files in `posts/YYYY-MM/YYYY-MM-DD/`
- Filename format: `YYYY-MM-DD_newsletter-slug_story-slug.md`
- Each file includes a metadata header (newsletter, source, date, status: draft)

## Approval gate (required before publishing)
After the pipeline runs, the user reviews posts via the Zimplixio Office dashboard
(`/posts` page) or directly in the `.md` files.
- **Approved posts:** status changed to `approved` in the dashboard or file header
- **Rejected posts:** status changed to `rejected` / file deleted
- Only approved posts get published to LinkedIn. No post goes live without
  explicit user approval. The agent never publishes directly.

## Post format
- Structure: hook → insight → CTA
- Voice: plain language, 8th grade reading level, opportunity-framed
- Forbidden: buzzwords, risk/fear framing, article re-reporting, source mentions, emojis, hashtags
- CTA: `https://zimplixio.com/book/`
- Length: 80–120 words

## Schedule
- Runs automatically **Tue/Thu/Fri at 1 PM** via local cron job
- Script: `run_pipeline.sh` — logs every run to `tmp/pipeline_run.log`

## Edge cases
- If `emails_raw.json` is older than 24 hours, `emails_parse.py` will warn.
  Re-run `emails_fetch.py` before proceeding.
- `context_fetch.py` caches results for 7 days — it will skip the fetch if the
  cache is fresh. This is intentional to avoid redundant PDF/URL parsing.
- If the API key is missing, `posts_generate.py` exits with a clear error.
- If a story has no clear SMB opportunity the filter deprioritizes it.
- The `Dragron CyberSecurity` Gmail label has a typo — preserved as-is per user preference.
- Never publish directly. All posts require human approval before going live.
