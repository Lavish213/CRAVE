# FAILURE_HANDLING

**Responsibility:** How failures are detected, logged, and recovered from in the menu ingestion pipeline.

---

## Failure Categories

| Category | Where caught | Log key |
|----------|-------------|---------|
| Place not found in DB | `menu_ingest.py` | `menu_ingest_place_not_found` |
| Place has no website | `menu_ingest.py` | `menu_ingest_no_website` |
| Grubhub live fetch failed | `menu_orchestrator.py` | `menu_orchestrator.grubhub_live_fetch_failed` |
| Website fetch failed | `menu_orchestrator.py` | `menu_orchestrator.website_fetch_failed` |
| Provider extraction failed | `menu_orchestrator.py` | `menu_orchestrator.provider_extraction_failed` |
| HTML fallback failed | `menu_orchestrator.py` | `menu_orchestrator.html_fallback_failed` |
| CSV ingest failed | `menu_orchestrator.py` | `csv_ingest_failed` |
| Unhandled exception | `menu_ingest.py` | `menu_ingest_failed` |
| HTTP timeout | `http_fetcher.py` | `RuntimeError("fetch_timeout_global")` |
| Batch place exception | `run_phase4_batch.py` | printed to stdout |

---

## Timeout

- HTTP timeout: `DEFAULT_TIMEOUT = 6.0s` (sync, per-request)
- Warmup timeout: `WARMUP_TIMEOUT = 4.0s`
- File: `app/services/network/http_fetcher.py`
- No asyncio — system is synchronous

---

## Batch Failure Tracking

`run_phase4_batch.py` tracks per-run:
- `stats.failed` — count of failed places
- `stats.errors` — list of `place_id: reason` strings
- `stats.by_blocked_reason` — grouped blocked reason counts
- Per-place status printed: `✓` extracted / `~` fallback / `-` skipped / `✗` failed

---

## Recovery Rules

- Extraction failures do NOT crash the batch — continue to next place
- Network failures log at DEBUG level, not propagated
- DB commit failures: rollback + log warning, continue
- Place with no website: skip silently (warning log only)
- Validation failure (< 2 distinct items): discard entire menu, log nothing written

---

## No `menu_scrape_log` Table

Failures are written to application logs only (no DB table for scrape results).
To audit failure rates, check batch stdout output or application logs.

---

## Re-run Safety

- Idempotent: re-running on a place that already has menu items → skipped (menu_items count > 0)
- `menu_source_url IS NULL` guard prevents re-probing already-discovered sources
