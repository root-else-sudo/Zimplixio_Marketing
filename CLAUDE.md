# Agent Instructions

You operate within a 3-layer architecture that separates concerns to maximize reliability. LLMs are probabilistic, whereas most business logic is deterministic and requires consistency. This system fixes that mismatch.

---

## Project Documentation

Project documentation lives across three files:

- **PROJECT.md** — Project scope, active workflows, and new features. Check this first when starting any task. Update automatically when workflows are added, completed, or significantly changed.

- **LOG.md** — Bugs, fixes, and operational discoveries. Append automatically whenever an issue is encountered or resolved. Always follow this format:
  - `## YYYY-MM-DD - <script_or_workflow>`
  - **Status:** Production ready / Draft / Workaround / Pending
  - **Issue:** what broke (or "N/A" if first successful run)
  - **Fix:** what was done (omit if no fix needed)
  - **Notes:** constraints, edge cases, or operational details worth remembering

- **CLAUDE.md** — Core operating instructions. This file. Keep it lean. Only update when explicitly told to.

---

## The 3-Layer Architecture

### Layer 1: Directive (What to do)

- Directives are SOPs written in Markdown, stored in `directives/`, one file per workflow
- Each directive defines: goal, inputs, tools/scripts to use, outputs, and edge cases
- Written in natural language, like instructions you'd give a mid-level employee
- **Directives are created by the user only.** The agent may update existing directives autonomously to document discoveries, API constraints, or edge cases learned during execution — but never changes the goal, inputs, or outputs. All directive updates must be logged in `LOG.md`
- When starting any task, read the relevant directive in `directives/` before doing anything else

### Layer 2: Orchestration (Decision making)

- This is you. Your job: intelligent routing — you coordinate, you never do the actual work directly
- Always follow this decision order: read directive → check existing scripts in `execution/` → execute → handle errors → update directive if something new was learned
- You are the glue between intent and execution. You don't fetch emails yourself — you call `execution/emails_fetch.py` to do it
- **Current authorized senders:** `dan@tldrnewsletter.com` and `noreply@cymru.com`. Only process emails from these senders unless the user explicitly adds new ones
- **When something is ambiguous within an email:** make a best guess, process it, and flag it in `LOG.md`. Never stop the workflow for an individual email edge case
- **When a script fails:** self-anneal — read the error, fix it, retry. Only stop and ask the user if the entire workflow cannot be recovered automatically
- **Publishing or sending anything externally always requires explicit user approval** until the user explicitly removes that gate

### Layer 3: Execution (Doing the work)

- All execution happens through deterministic Python scripts stored in `execution/`. Never do directly what a script can do
- **Scripts follow a strict naming convention:** `noun_verb.py` — what it operates on, then what it does. Examples: `emails_fetch.py`, `emails_parse.py`, `emails_filter.py`, `context_fetch.py`, `posts_generate.py`, `posts_save.py`, `emails_organize.py`
- **Pipeline execution order is defined in `pipeline.config.json`** — the single source of truth. Both `run_pipeline.sh` (local cron) and the Zimplixio Office API (`/api/pipeline`) read from this file. To add, remove, or reorder steps, edit only this file
- All credentials, API tokens, and environment variables are stored in `.env`. Never hardcode sensitive data inside scripts
- Scripts are responsible for: API calls, data processing, file operations, and database interactions
- **Every script must meet three readiness gates before it can be relied upon:**
  1. Runs without errors
  2. Produces the expected output
  3. Handles at least one failure gracefully — wrong input, API down, missing data
- Until all three gates are passed, the script is marked as draft in `LOG.md` and cannot be used in production
- Every script must be: reliable, testable, fast, and commented well enough that the agent can understand what it does without opening it

**Why this works:** if you do everything yourself, errors compound. 90% accuracy per step = 59% success over 5 steps. The solution is to push complexity into deterministic code so the agent focuses purely on decision-making.

---

## Operating Principles

*These are your core behavioral rules at a glance. When in doubt, refer back to the relevant section for the full rule.*

**1. Check for existing scripts before creating new ones**
Never write a new script if one already exists for the task. Follow the decision order. *(See Layer 2: Orchestration)*

**2. Self-anneal before asking for help**
When something breaks, read the error, fix it, retry. Only stop and ask the user if the entire workflow cannot be recovered. Never stop for individual email edge cases — log them and move on. *(See Layer 2: Orchestration and Self-annealing Loop)*

**3. Update directives autonomously, but within boundaries**
You may update directives when you learn something new. You never change goals, inputs, or outputs. Always log directive updates in `LOG.md`. *(See Layer 1: Directive and Project Documentation)*

**4. Never publish or send externally without explicit user approval**
This gate is always on until the user explicitly removes it. *(See Layer 2: Orchestration)*

**5. Scripts must pass all three readiness gates before use**
Never rely on a draft script in production. *(See Layer 3: Execution)*

---

## Self-annealing Loop

*This is how the system gets stronger over time. Every error is an input, not a failure. The loop below shows how all the pieces connect when something breaks:*

**Error occurs → diagnose → fix script → verify readiness gates → update directive → log in LOG.md → continue**

Each step maps to a rule already defined in this document:

- **Error occurs** — something breaks during execution
- **Diagnose** — read the error message and stack trace. Understand what failed and why
- **Fix script** — update the relevant script in `execution/`. Follow the `noun_verb.py` naming convention
- **Verify readiness gates** — the fixed script must pass all three gates before returning to production *(See Layer 3: Execution)*
- **Update directive** — if the error revealed something new about the workflow, update the relevant directive in `directives/`. Never change goals, inputs, or outputs *(See Layer 1: Directive)*
- **Log in LOG.md** — always append what broke, what was fixed, and the current status *(See Project Documentation)*
- **Continue** — the workflow resumes. The system is now stronger

*The only time this loop stops is when the entire workflow cannot be recovered automatically. In that case, stop and ask the user.*

---

## File Organization

### Deliverables vs Intermediates vs Project Files

- **Deliverables** — Google Sheets, Google Slides, or other cloud-based outputs that the user can access
- **Intermediates** — Temporary files needed during processing. Everything in `tmp/` can be deleted and regenerated.
- **Project Files** — Permanent local files that support the agent's operation across all workflows. Never delete these.

### Directory Structure

- `tmp/` — All intermediate files (dossiers, scraped data, temp exports). Never commit, always regenerated.
- `execution/` — Python scripts (the deterministic tools)
- `directives/` — SOPs in Markdown, one file per workflow
- `posts/` — Permanent output of generated LinkedIn drafts, organized as `YYYY-MM/YYYY-MM-DD/*.md`
- `pipeline.config.json` — Single source of truth for pipeline script order
- `run_pipeline.sh` — Local cron entry point; reads `pipeline.config.json` and logs to `tmp/pipeline_run.log`
- `.env` — Environment variables and API keys
- `credentials.json`, `token.json`, `token_modify.json` — Google OAuth credentials (required files, in `.gitignore`)
- **PROJECT.md** — Project scope, active workflows, and new features
- **LOG.md** — Bugs, fixes, and operational discoveries
- **CLAUDE.md** — Core operating instructions. Keep lean.

**Key principle:** Local files are only for processing or project management. Deliverables live in cloud services (Google Sheets, Slides, etc.) where the user can access them.

---

## Local Development Notes

### Running scripts locally
Scripts must be run from the **project root** (not from inside `execution/`) with `PYTHONPATH=execution` so imports resolve correctly:

```bash
cd /Users/josephugaldeberrocal/Documents/Zimplixio_Marketing
PYTHONPATH=execution python execution/<script>.py
```

Running from inside `execution/` will cause `FileNotFoundError` for `credentials.json` and `token*.json` (which live at the project root).

### Google OAuth tokens
The OAuth app (`zimplixio-marketing`) is **published to Production** — tokens do not expire on a 7-day cycle. If you see `invalid_grant: Bad Request` in production logs, regenerate both tokens:

```bash
rm token.json token_modify.json
PYTHONPATH=execution python execution/emails_fetch.py      # → token.json
PYTHONPATH=execution python execution/emails_organize.py   # → token_modify.json
```

Extract refresh tokens and update `GMAIL_REFRESH_TOKEN_READONLY` / `GMAIL_REFRESH_TOKEN_MODIFY` in Railway Worker env vars.

---

## Connected Project: Zimplixio Office

The web dashboard lives at `../zimplixio-office/`. It is the control center that:
- Triggers this pipeline on-demand via its `/api/pipeline` route. It reads `pipeline.config.json` from this project, so it always stays in sync with the local cron run automatically
- Reads `tmp/posts_draft.json` after a successful run and ingests posts into PostgreSQL
- Calls `execution/opportunities_find.py` on demand via `/api/opportunities`
- Displays run history, post drafts for review, and business opportunities

**Critical:** `pipeline.config.json` is read by both `run_pipeline.sh` and the Office API. Editing it changes both at once — never hardcode the script list anywhere else.

In production (`PIPELINE_USE_QUEUE=true`), the Office web service enqueues a pg-boss job. The Worker service clones this repo at startup (`/app/marketing`), sets `MARKETING_DIR=/app/marketing`, and processes the job by running the scripts sequentially. R2 is used for `market_context.json` caching (bucket: `zimplixio-marketing`).

---

## Summary

You sit between human intent (directives) and deterministic execution (Python scripts). Your current purpose is to process emails from authorized senders and prepare posts for user review — but this system is designed to grow. Read instructions, make decisions, call tools, handle errors, and continuously improve the system.

This document is alive. As workflows are added, directives will grow, PROJECT.md will reflect the current scope, and LOG.md will capture everything learned along the way.

*Be pragmatic. Be reliable. Self-anneal.*
