# Zimplixio Marketing — Project State

## Purpose
Automate a pipeline that turns newsletter emails into LinkedIn post drafts for Zimplixio, ready for human review and approval before publishing. Pipeline runs Tue/Thu/Fri at 1 PM via local cron job.

---

## Active Workflow: Email → LinkedIn Posts

### Pipeline (fully operational)

| Step | Script | Input | Output | Status |
|---|---|---|---|---|
| 1 | `emails_fetch.py` | Gmail API | `tmp/emails_raw.json` | Production |
| 2 | `emails_parse.py` | `tmp/emails_raw.json` | `tmp/emails_parsed.json` | Production |
| 3 | `emails_filter.py` | `tmp/emails_parsed.json` | `tmp/emails_filtered.json` | Production |
| 4 | `context_fetch.py` | PDF + fixed URLs | `tmp/market_context.json` (cached 7 days) | Production |
| 5 | `context_search.py` | Tavily search → appends to `tmp/market_context.json` | `tmp/market_context.json` (updated) | Production |
| 6 | `posts_generate.py` | `tmp/emails_filtered.json` + `tmp/market_context.json` | `tmp/posts_draft.json` | Production |
| 7 | `posts_save.py` | `tmp/posts_draft.json` | `posts/YYYY-MM/YYYY-MM-DD/*.md` | Production |
| 8 | `emails_organize.py` | Gmail API | Labels and archives processed emails | Production |

### Run order
Defined in `pipeline.config.json` — the single source of truth for script execution order. Both `run_pipeline.sh` (cron) and the Zimplixio Office API (`/api/pipeline`) read from this file. To add, remove, or reorder steps, edit only this file.

```json
["emails_fetch", "emails_parse", "emails_filter", "context_fetch",
 "context_search", "posts_generate", "posts_save", "emails_organize"]
```

### Standalone scripts (not in main pipeline)

| Script | Purpose | Output |
|---|---|---|
| `folders_manage.py` | Creates missing day folders in `posts/` from April 1 to today | Folder structure |
| `opportunities_find.py` | Finds 5 SMB opportunities via Tavily + Claude | `tmp/opportunities.json` |

`opportunities_find.py` is triggered on-demand by the Zimplixio Office dashboard (`POST /api/opportunities`). It is not part of the email pipeline.

---

## Authorized Email Sources
- `dan@tldrnewsletter.com` — TLDR newsletters (AI, InfoSec, Founders, IT, DevOps, Marketing, Dev)
- `noreply@cymru.com` — DragonNews Bytes (cybersecurity)

---

## Post Format
- Structure: hook → insight → CTA
- Voice: plain language, 8th grade reading level, opportunity-framed, no buzzwords, no emojis, no hashtags
- CTA: `https://zimplixio.com/book/`
- Length: 80–120 words
- Output: individual `.md` files per post

---

## Post Folder Structure
`posts/YYYY-MM/YYYY-MM-DD/YYYY-MM-DD_newsletter-slug_story-slug.md`

Folder structure managed by `execution/folders_manage.py`.

---

## Schedule
- **Production (Railway):** triggered on-demand from the Zimplixio Office dashboard (`crm.zimplixio.com`) — web service enqueues a pg-boss job, Worker service picks it up and runs the pipeline
- **Local (cron):** runs automatically **Tue/Thu/Fri at 1 PM** via `run_pipeline.sh` — logs to `tmp/pipeline_run.log`
- Note: the Zimplixio Office agent record displays `0 11 * * 1-5` as its cron schedule — this is cosmetic/display only and does not reflect the actual cron timing.

---

## Directive
See `directives/email_to_linkedin_posts.md` for the full SOP including edge cases and approval gate.
