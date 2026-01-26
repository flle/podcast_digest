# Podcast Digest – AI Agent Instructions

## Project Purpose
Automated daily workflow to monitor RSS podcast feeds, deduplicate new episodes, transcribe audio via ASR, generate LLM-powered summaries, and deliver digests via HTML email. Orchestrated via GitHub Actions; state persists in `state/state.json` to prevent reprocessing.

## Architecture Overview

**Core Pipeline Flow:**
```
RSS Feed Parse (feeds.py) → Dedupe by Episode Key (storage.py) → 
Optional ASR Transcription (asr.py) → LLM Summarization (summarizer.py) → 
HTML Rendering (templates/email.html) → Email Delivery (mailer.py)
```

**Key Components:**
- `src/main.py` – Orchestration entry point; handles mode switching (BOOTSTRAP, SMOKE_TEST, DRY_RUN, FORCE_LATEST_N)
- `src/feeds.py` – RSS/feed parsing via `feedparser`; Episode deduplication by stable episode key
- `src/asr.py` – Optional audio transcription using OpenAI Whisper or gpt-4o-mini-transcribe; includes audio download, chunking via ffmpeg, caching
- `src/summarizer.py` – LLM calls (OpenAI/Gemini); prompt injection from `config/prompts.yml`
- `src/storage.py` – JSON state persistence (`state/state.json`); tracks processed episodes, ASR cache (`state/asr_cache.json`)
- `src/mailer.py` – SMTP email delivery with retry logic; respects DRY_RUN flag
- `templates/email.html` – Jinja2 email template

## Configuration & Environment

**Feed Configuration:** `config/feeds.yml` defines RSS feeds with `id`, `type` (podcast), `url`.

**Prompt Templates:** `config/prompts.yml` contains LLM prompts injected at runtime.

**Environment Variables** (set in `.github/workflows/podcast_digest.yml`):
- `LLM_PROVIDER` – "openai" or "gemini"
- `MODEL_TEXT` – LLM model (e.g., "gpt-4o-mini")
- `ASR_ENABLED`, `ASR_MODEL`, `ASR_CACHE_ENABLED`, `ASR_MAX_DOWNLOAD_MB`, `ASR_CHUNK_MINUTES`
- `SMOKE_TEST`, `DRY_RUN`, `BOOTSTRAP`, `FORCE_LATEST_N` – operational modes
- `MAX_EPISODE_AGE_DAYS`, `BOOTSTRAP_LATEST_N` – filtering thresholds
- SMTP & OpenAI credentials from GitHub secrets

## Critical Patterns & Conventions

**Episode Deduplication:**
Episodes are keyed by a stable identifier (typically feed ID + pub date or URL). Stored in `state/state.json`; if episode key exists and was successfully processed, it's skipped.

**Operational Modes (Env Flags):**
- `BOOTSTRAP=1` – Cold start: fetch & process last N episodes without state history
- `SMOKE_TEST=1` – Parse feeds, skip LLM/ASR/mail; test connectivity only
- `DRY_RUN=1` – Process fully but don't send email
- `FORCE_LATEST_N=N` – Re-process last N episodes regardless of state
- Default (all 0) – Incremental: process only new episodes since last state

**ASR & Audio Handling:**
If `ASR_ENABLED=1`, download audio (max `ASR_MAX_DOWNLOAD_MB`), optionally transcode via ffmpeg, chunk into `ASR_CHUNK_MINUTES` pieces, transcribe, and cache in `asr_cache.json`. Transcript is passed to summarizer.

**Error Resilience:**
State is saved incrementally after each episode; partial failures don't lose progress. Retries configured for LLM calls (`LLM_RETRIES`, `LLM_BACKOFF_S`) and SMTP (`SMTP_RETRIES`, `SMTP_TIMEOUT`).

## Common Tasks

**Add a new feed:** Edit `config/feeds.yml`, add entry with `id`, `type: podcast`, `url`. State will auto-track.

**Modify summarization prompt:** Update `config/prompts.yml`. All LLM calls read from this file.

**Test locally (smoke test):** Set `SMOKE_TEST=1`, run `python src/main.py`. Validates feed parsing without invoking LLM/ASR.

**Force reprocess last N episodes:** Set `FORCE_LATEST_N=N` to override state and reprocess.

**Enable ASR transcription:** Set `ASR_ENABLED=1`, choose model, configure `ASR_CHUNK_MINUTES` for long audio. Requires ffmpeg installed.

**Debug state:** Inspect `state/state.json` for processed episodes and `state/asr_cache.json` for transcripts.

## Dependencies & Tools

- `feedparser` – RSS parsing
- `openai` – LLM & Whisper API
- `PyYAML` – Config loading
- `Jinja2` – Email template rendering
- `ffmpeg` (system) – Audio re-encoding (if ASR chunking enabled)
- Python 3.11+

## GitHub Actions Workflow

`.github/workflows/podcast_digest.yml` runs on daily schedule (05:00 UTC = 06:00/07:00 Zürich) or manual dispatch. Checks out repo, sets up Python 3.11, reads secrets from environment, runs `main.py`, and commits updated `state/state.json` back to repo.

## Testing & Debugging

- **Local run:** `SMOKE_TEST=1 python src/main.py` (parse feeds only)
- **Dry run:** `DRY_RUN=1 python src/main.py` (full processing, no email)
- **Reset state:** Delete or edit `state/state.json` to re-process episodes
- **Check logs:** Inspect workflow logs in GitHub Actions for env & error traces
