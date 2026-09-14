# MENU_INGEST_SYSTEM

**Responsibility:** End-to-end pipeline from place selection → menu extraction → DB write.

---

## Pipeline Layers

```
Place selection (batch script)
  → MasterDataOrchestrator.ensure_place()
    → MenuOrchestrator.run_for_place()
      → Source priority: Grubhub → CSV → governed provider/public source → HTML fallback
      → MenuWriter.write_items()
        → menu_items table
      → MenuImageBridge
        → place_images table (via Phase 3 classifier)
    → materialize_menu_truth()
      → has_menu flag updated on Place
```

---

## Entry Points

| Script | Purpose |
|--------|---------|
| `scripts/run_phase4_batch.py` | Batch extraction (200–500 places at a time) |
| `scripts/run_menu_worker.py` | Continuous worker loop |
| `scripts/discover_menu_sources.py` | Probe Place.website → populate menu_source_url |
| `app/services/menu/menu_ingest.py` | Single-place programmatic entry |
| `POST /api/v1/places/{place_id}/menu/submit` | User/restaurant-submitted menu, staged for admin review |
| `GET/POST /api/v1/moderation/menu-submissions` | Admin review queue and approve/reject flow |

---

## Source Priority + Governance

CRAVE does **not** treat every URL as a scrape target. Source URLs are first
classified by `app/services/menu/fetch/fetch_strategy_router.py`.

1. **Manual/reviewed source** — `menu_submissions` approval writes
   `PlaceClaim(field="menu_item", source="user_submission")`, then runs the
   same `materialize_menu_truth()` → `MenuPublisher` pipeline as scrapers.
   This is the correct fallback for restaurant owners/users when provider
   access is blocked.
2. **CSV** — `place.menu_csv_path` if set.
3. **Official/public provider source** — public Square/Square Site, Popmenu,
   Clover-like sources only when reachable without bypassing auth/bot walls.
4. **Official-API-required provider** — Toast and ChowNow ordering/menu URLs are
   classified as `fail_fast` with `blocked_reason="provider_api_required"`.
   The correct path is an official provider connector or a reviewed manual menu
   submission, not Playwright/scraping escalation.
5. **Aggregator/auth source** — Grubhub requires credentials; delivery
   aggregators and redirect traps are fail-fast.
6. **Public HTML fallback** — JSON-LD → hydration → structured HTML parsing for
   ordinary restaurant websites.
7. **Google** — fallback only, marked `fallback_used=true`.

### Blocked-source reasons

| Reason | Meaning | Next action |
| --- | --- | --- |
| `provider_api_required` | Toast/ChowNow/provider-owned ordering surface needs official/restaurant authorization. | Build connector or ask restaurant/user to submit menu for review. |
| `missing_auth` | A source type has an auth path but credentials are not configured. | Configure approved credentials or skip. |
| `delivery_aggregator` | Third-party delivery surface, not authoritative menu truth. | Do not publish from it by default. |
| `redirect_trap` | Yelp/Tripadvisor/OpenTable/etc. link does not expose menu truth. | Skip or find official site/menu. |
| `captcha_domain` | Known bot-wall surface. | Do not burn scheduled retries; use manual review/provider access. |

---

## DB Tables Written

| Table | Written by | Key fields |
|-------|-----------|------------|
| `menu_submissions` | User/restaurant submission route | pending/approved/rejected staged menu payload |
| `place_claims` | Scrapers and approved user submissions | menu_item claims with source/provenance |
| `place_truths` | materialize_menu_truth | canonical resolved menu JSON |
| `menu_items` | MenuPublisher | public serving cache: name, section, price_cents, fingerprint, place_id |
| `places` | materialize_menu_truth / worker | has_menu, menu_source_url |
| `place_images` | MenuImageBridge | url, content_type, quality_score, visibility_status |

---

## Connection Pool

- `pool_size=20`, `max_overflow=40`, `pool_recycle=1800`, `pool_pre_ping=True`
- File: `app/db/session.py`

---

## Batch Run Command

```bash
cd backend
python scripts/run_phase4_batch.py --limit 200 --priority smart          # preview only
python scripts/run_phase4_batch.py --limit 200 --priority smart --run    # executes
```

Priority options: `grubhub | provider | web | all | smart`

`--limit` is required (capped at 200) and `--run` is required to actually
execute -- same preview-first discipline as `run_menu_backlog_canary.py`.
`scripts/run_menu_backlog_canary.py` is the safest first-run path for a
reviewed target list. Its preview now shows the selected source strategy,
provider, blocked reason, and auth requirement so Toast/ChowNow/provider walls
can be excluded or intentionally sent to manual/provider-access queues before
execution.

The same governance applies inside the advanced extractor:

- direct provider extraction,
- discovered API/GraphQL endpoints,
- embedded menu iframes,
- browser escalation.

This matters because an ordinary restaurant website may embed a protected
Toast/ChowNow ordering surface even when the restaurant's own homepage is
public. Public extraction remains enabled for normal HTML, JSON-LD, hydration
state, PDFs, Square/Square Site, Popmenu, and other reachable sources; provider
walls remain blocked until official access or reviewed manual submission.

---

## Rules

- Each place processed once per batch run (deduped by place_id)
- Commit every 10 places
- Checkpoint log every 50 places
- Menu items only written if `validated_items >= MIN_CANONICAL_ITEM_COUNT (2)`
- Item images → Phase 3 pipeline (classifier → visibility → primary selector). No bypass.
- Protected providers are access-governance states, not parser bugs. Do not
  “fix” them by scraping harder.
- User/restaurant menu submissions are not trusted directly; approval is
  required before they become claims/truth/menu rows.

---

## Manual add / verify paths that exist today

| Need | Current path | Status |
| --- | --- | --- |
| Add a photo to an existing place | App upload flow via `requestUpload()` / `confirmUpload()` with `photo_type="food"` or `"menu"` | Exists; menu photos trigger OCR path. |
| Add a menu manually | `POST /api/v1/places/{place_id}/menu/submit` then admin review under `/api/v1/moderation/menu-submissions` | Exists backend; frontend/admin UX may still need surfacing. |
| Approve/reject a submitted menu | `POST /api/v1/moderation/menu-submissions/{id}/review` | Exists; admin gated. |
| Add a brand-new place | App `add-spot` creates a `DiscoveryCandidate`; promotion creates the real `Place` later | Exists, but media/menu attachment to not-yet-promoted candidates is intentionally limited. |
| Official Toast/ChowNow sync | Provider connector with restaurant/partner credentials | Not implemented. |
