## 2026-06-02 - posts_save.py removed from pipeline

- **Status:** Production ready
- **Issue:** N/A — deliberate removal
- **Notes:**
  - `posts_save.py` was removed from `pipeline.config.json`. The script still exists but is no longer part of the pipeline.
  - Posts are ingested into PostgreSQL by the Zimplixio Office worker after all scripts complete. The local `.md` files in `posts/` served no purpose in production (ephemeral container filesystem) and the CRM dashboard replaces them entirely.
  - `posts_save.py` can still be run manually for local inspection if needed.

---

## 2026-06-01 - Production deployment & OAuth

- **Status:** Production ready
- **Issue:** Pipeline failed on first production run with `invalid_grant: Bad Request` on `emails_fetch.py`. Root cause: Google OAuth app was in **Testing** mode, causing refresh tokens to expire after 7 days. Token in Railway had been issued ~30 days prior.
- **Fix:** Published OAuth app to Production in Google Cloud Console (Google Auth Platform → Audience → Publish app). Deleted both `token.json` and `token_modify.json`, re-ran OAuth flows for both scopes, extracted fresh refresh tokens, updated Railway Worker env vars `GMAIL_REFRESH_TOKEN_READONLY` and `GMAIL_REFRESH_TOKEN_MODIFY`.
- **Notes:**
  - Scripts must run from project root with `PYTHONPATH=execution python execution/<script>.py` — running from inside `execution/` causes `FileNotFoundError` for `credentials.json`
  - R2 bucket `zimplixio-marketing` created in Cloudflare; token uses "Account API Token" (S3-compatible), not the `cfat_` Cloudflare API token
  - Python `.venv` must be rebuilt for arm64 on Apple Silicon if architecture changes: `PIPENV_VENV_IN_PROJECT=1 pipenv install`
  - Pipeline verified end-to-end in production: all 8 steps completed, posts ingested to PostgreSQL

---

## 2026-05-02 - opportunities_find.py

- **Status:** Production ready
- **Issue:** N/A — created as part of Zimplixio Office integration
- **Notes:**
  - Runs 5 Tavily searches, one per SMB sector (Professional Services, Construction & Trades, Healthcare & Wellness, Retail & E-commerce, Logistics & Distribution)
  - Calls Claude (claude-sonnet-4-6) to structure each result into: title, sector, signal, zimplixioAngle, actions (5 items)
  - Output saved to `tmp/opportunities.json` and consumed by `/api/opportunities POST` in the Office dashboard
  - Not part of the main email pipeline — triggered on-demand from the dashboard

---

## 2026-05-02 - context_fetch.py

- **Status:** Production ready
- **Issue:** N/A — created to enrich post generation with market context
- **Notes:**
  - Fetches SMB insights from a local PDF (Salesforce SMB Trends report) and 3 fixed URLs
  - Results are cached in `tmp/market_context.json` for 7 days to avoid redundant parsing
  - Maps insights to Zimplixio service definitions for relevance scoring
  - Must run before `posts_generate.py` to ensure context is available

---

## 2026-05-02 - context_search.py

- **Status:** Production ready
- **Issue:** N/A — created to keep market context fresh between cache refreshes
- **Notes:**
  - Runs one Tavily search per pipeline run, rotating through 8 predefined SMB-focused queries
  - Appends new insights to `tmp/market_context.json` (does not overwrite cached data)
  - Query rotation prevents repetition across runs
  - Must run after `context_fetch.py` and before `posts_generate.py`

---

## 2026-05-02 - folders_manage.py

- **Status:** Production ready
- **Issue:** N/A — utility script, not in main pipeline
- **Notes:**
  - Creates all missing `posts/YYYY-MM/YYYY-MM-DD/` folders from April 1, 2026 to today
  - Creates next month's folder on the last day of each month
  - Safe to run multiple times (idempotent — skips existing folders)
  - Run manually as needed, not as part of the pipeline

---

## 2026-04-30 - emails_organize.py

- **Status:** Production ready
- **Issue:** Script created a new `Education/Dragon CyberSecurity` label instead of using the existing `Dragron CyberSecurity` label. 6,423 Cymru emails were moved to the wrong label.
- **Fix:** Moved all emails back to `Dragron CyberSecurity` (Label_18), deleted the incorrectly created label, updated `AUTHORIZED_SENDERS` to use the exact existing label name `Dragron CyberSecurity`.
- **Note:** The existing label has a typo ("Dragron" instead of "Dragon") — preserved as-is per user preference.

---

## 2026-04-29 - emails_fetch.py

- **Status:** Production ready
- **Issue:** N/A — first successful run
- **Notes:** 
  - Fetched 20 emails from authorized senders
  - token.json generated and stored at project root
  - Unicode characters in subject lines and snippets need cleanup — handled in emails_parse.py

---

## 2026-04-29 - emails_parse.py

- **Status:** Production ready
- **Issue:** N/A
- **Notes:**
  - Handles two email formats: TLDR (snippet-based) and DNB (structured Title/Source/Date/Excerpt)
  - Strips zero-width spaces and decodes HTML entities from snippets
  - Parses dates to ISO 8601
  - Unknown senders passed through with type=unknown

---

## 2026-04-29 - emails_filter.py

- **Status:** Production ready
- **Issue:** Initial version passed macro/financial news (stock drops, revenue misses) that had no SMB opportunity angle
- **Fix:** Added NEGATIVE_KEYWORDS list penalising macro finance and arrest stories; added OPPORTUNITY_KEYWORDS bonus for signals with actionable SMB potential
- **Notes:** Selects top 5 stories by score. Scores printed on each run for review.

---

## 2026-04-29 - posts_generate.py

- **Status:** Production ready
- **Issue 1:** `load_dotenv()` not pushing ANTHROPIC_API_KEY into `os.environ` — key read by dotenv_values but not available via os.getenv
- **Fix:** Replaced `load_dotenv()` with `dotenv_values()` using explicit path, then manually updates `os.environ`
- **Issue 2:** First prompt version produced news summaries, not Zimplixio marketing assets. Risk/fear framing, buzzwords, article re-reporting.
- **Fix:** Rewrote system prompt. News is a signal only. Posts are opportunity-framed, plain language (8th grade), Zimplixio POV throughout. Forbidden buzzword list added.
- **Notes:** Model: claude-sonnet-4-6. Max tokens: 400. One API call per filtered story.

---

## 2026-04-29 - posts_save.py

- **Status:** Production ready
- **Issue:** N/A
- **Notes:**
  - Saves to posts/YYYY-MM/YYYY-MM-DD/ using source date from parsed email
  - Creates folders as needed (os.makedirs)
  - Filename: YYYY-MM-DD_newsletter-slug_story-slug.md
