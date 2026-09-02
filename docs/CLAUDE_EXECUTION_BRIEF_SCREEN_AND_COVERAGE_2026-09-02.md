# Claude execution brief: first user journey + free-source coverage

Date: 2026-09-02  
Author: Codex  
Starting point: current `main` at or after `e6b7d9b`

## Mission

Own two separate tracks, in order, without mixing their commits or evidence:

1. Make the first useful CRAVE journey feel complete: **Feed → Place Detail → Save → Craves**.
2. Increase real menu and photo coverage using the existing free-source systems, but only through bounded, reviewable canaries.

Population may improve the underlying data, but it does not replace resilient UI. A prettier fallback must not be reported as improved data coverage.

## Verified starting baseline

Re-measure before production work. The latest committed baseline says:

| Metric | Count | Coverage |
| --- | ---: | ---: |
| Active places | 37,761 | 100% |
| Places with a materialized menu | 1,005 | 2.66% |
| Places with any public image | 15,313 | 40.55% |
| Places with a primary image | 13,802 | 36.55% |
| Places with a known website | 14,133 | 37.43% |
| Website-backed places without a menu | 13,128 | candidate pool only |
| Website-backed places without a public image | 7,816 | candidate pool only |

These figures come from `CRAVE_STATUS.md`; they are historical until reproduced against production. Never claim a percentage increase without before/after queries using the same denominator and visibility rules.

## Non-negotiable operating rules

- Read `AGENTS.md`, `.agent-bridge/PROTOCOL.md`, `.agent-bridge/STATE.md`, both inboxes, `CRAVE_STATUS.md`, `docs/POPULATION_RELEASE_PASS_2026-09-01.md`, `docs/POPULATION_READINESS.md`, and `docs/SCHEDULER_WORKER_ROLLOUT.md` first.
- Claim one track at a time in `.agent-bridge/STATE.md`. Use a fresh `claude/` branch and PR for each independently reviewable outcome.
- Verify the branch contains current `main` before testing or touching production.
- Use test-driven development for behavioral changes: demonstrate the failing regression, implement the smallest fix, then rerun focused and required suites.
- Preserve all existing dirty files. Never reset, clean, or reformat unrelated work.
- Never print, commit, paste, or place secrets in a handoff. Use Railway references and existing secret stores.
- Do not use Google Places, paid LLM extraction, Bright Data, Firecrawl Cloud, Apify, proxy services, or any metered fallback in the free-source track.
- Respect robots.txt, source terms, rate limits, copyright, and provenance. Do not bypass CAPTCHAs, access controls, TLS fingerprints, or anti-bot systems.
- Do not hotlink unknown third-party images. Only stage permitted official-site/provider media with source and license/provenance evidence.
- Do not enable recurring `menu_enrichment`, `image_ingestion`, discovery, scoring, ranking, OSM, or Overture jobs as a shortcut.
- New image rows remain hidden/non-primary until separately reviewed. Suspicious menus remain unpublished or quarantined.
- A canary with zero useful results is valid evidence, not permission to widen the batch.

## Track 1 — first user journey

### User outcome

As a hungry user, I can open Feed, understand why a place is worth considering, open a useful Place Detail screen, save it once, and find that same place once in Craves without blank-media walls or duplicate representations.

### Required work

1. Reproduce the journey on a fresh current-main iOS simulator build. Save screenshots and determine whether prior screenshots came from a stale build.
2. Fix shared missing-media behavior first. A place with no usable image must render a compact, intentional identity state; it must not reserve a giant empty hero/card area.
3. Refine Feed around decisions, not catalog dumping:
   - Decision Session is the primary decision surface when data exists.
   - Preserve explainability and tier semantics.
   - Avoid oversized low-information cards and repeated labels.
   - Loading, empty, error, signed-out, and partial-data states must be distinct.
4. Refine Place Detail without undoing the established order in `docs/doctrine/CRAVE_PLACE_DETAIL_SPEC.md`: hero → identity → decision strip → why this fits → primary CTA → actions → menu → social.
5. Make Save → Craves coherent:
   - one place appears once in the primary saved-place list;
   - preserve source/reason metadata from social-link additions;
   - do not delete or collapse distinct domain records merely to hide a UI duplicate;
   - removal, visited state, notes, and navigation remain correct.
6. Validate Dynamic Type, VoiceOver labels/order, 44×44pt minimum targets, contrast, reduced motion, narrow devices, long names, no-image places, and offline/API failure.

### Acceptance criteria

- [ ] Fresh screenshots cover Feed, Place Detail, saved confirmation, and Craves.
- [ ] A no-image Feed card consumes materially less vertical space than an image-backed card and clearly communicates that no photo is available.
- [ ] No place is presented twice as two indistinguishable saved entries.
- [ ] The user can explain why each main Feed choice is shown without debug UI.
- [ ] Save and unsave provide accessible feedback and remain correct after reload.
- [ ] The Place Detail hierarchy is preserved unless tests and screenshots prove a better change.
- [ ] Focused tests, full frontend Jest, `tsc --noEmit`, and the relevant Playwright journey pass.
- [ ] UI changes have before/after screenshots in the PR.

### Explicit non-goals

- Do not redesign Map, Search, Profile, onboarding, or ranking algorithms in this PR.
- Do not fabricate photos or use generic stock art as restaurant evidence.
- Do not add a video tab or change the settled video-home decision.
- Do not combine the UI PR with extractor, scheduler, database, or production changes.

## Track 2 — free-source menu and photo coverage

### Objective

Prove which existing free extractors can safely increase recall, fix only evidence-backed extractor gaps, then run small exact-ID production canaries. The goal is verified public coverage gain without contaminated menus, stale venues, copyrighted hotlinks, paid calls, or uncontrolled scheduler load.

### Phase A — current production truth (read-only)

1. Confirm deployed SHA includes current `main` and all recent population hardening.
2. Confirm `CRAVE-scheduler` still has exactly `moderation_queue_health_check`, `share_parser`, `image_processing_recovery`, and `video_processing`.
3. Confirm all forbidden recurring jobs remain absent.
4. Run the existing read-only menu report globally and for one target city:

   ```bash
   cd backend
   python scripts/menu_coverage_report.py
   python scripts/menu_coverage_report.py --city-slug oakland
   ```

5. Produce equivalent read-only image counts using the definitions in `CRAVE_STATUS.md`: active-place denominator, public image, primary image, known website, website/no-public-image, unclassified, hidden, failed, and source/provider breakdown.
6. Save sanitized output in a dated evidence document. Never expose connection strings or tokens.

### Phase B — stratified target selection

Do not select only the highest-ranked places. Build 3–5-target cohorts that reveal distinct failure modes:

- official site with visible HTML or JSON-LD menu;
- linked Toast/Clover/Popmenu/Square/ChowNow/Olo provider;
- official first-party XHR/JSON;
- JavaScript-rendered official site;
- PDF menu on the official domain;
- redirect, parked, stale, or closed site;
- known CAPTCHA response for diagnosis only—never bypass it;
- website-backed place with no photo;
- provider-backed place with permitted image metadata;
- chain location where matching must remain location-specific.

Record exact place ID, name, address, website, selection reason, existing menu/image counts, and expected source shape. Manually verify every target is the correct active entity before execution.

### Phase C — sandbox proof before production

For each evidenced extractor gap:

1. Capture a lawful, sanitized fixture or replay payload.
2. Add a failing regression test for the missed data or contamination bug.
3. Make the smallest bounded change in the existing router/provider architecture; do not create a parallel pipeline.
4. Test false positives: navigation text, merchandise, catering boilerplate, duplicate variants, unrelated JSON, logos, icons, tracking pixels, map tiles, and stale venue media.
5. Preserve provider, source URL/type, timestamps, image provenance, and confidence through materialization.
6. Run focused extractor tests, menu guards or image invariants, and the full backend suite.

Existing entry points:

- `backend/scripts/run_menu_extraction_corpus.py` — deterministic extractor corpus.
- `backend/scripts/discover_menu_sources.py` — official-site provider discovery.
- `backend/scripts/run_menu_backlog_canary.py` — exact-ID menu canary.
- `backend/scripts/run_free_image_canary.py` — exact-ID, maximum-10, Google-unreachable image canary.
- `backend/scripts/menu_coverage_report.py` — read-only menu baseline.
- `backend/scripts/run_phase3_image_backfill.py` — local/no-external classification only; classification is not acquisition.

### Phase D — menu production canary

1. Choose at most 10 reviewed targets from the strongest sandbox cohorts.
2. Preview only:

   ```bash
   cd backend
   python scripts/run_menu_backlog_canary.py --place-ids-file /tmp/reviewed-menu-canary.txt
   ```

3. Review exact count, active entity, existing-menu state, source URL, and failure history.
4. Execute only after reviewing the exact set:

   ```bash
   python scripts/run_menu_backlog_canary.py \
     --place-ids-file /tmp/reviewed-menu-canary.txt \
     --run --confirm-count N
   ```

5. Inspect every materialized menu: distinct names, sections, duplicate ratio, provider lineage, source URL, price plausibility, unrelated products, and published state.
6. Quarantine any contaminated result immediately and record exact affected IDs.
7. Re-run the baseline and report `attempted`, `materialized`, `clean`, `quarantined`, `errors`, and net coverage change.

Stop if a result has cross-venue contamination, lacks provenance, publishes low-quality data, causes paid-provider traffic, or changes more rows than reviewed.

### Phase E — photo production canary

1. Choose at most 10 active exact-ID targets with an official source and zero image rows.
2. Preview:

   ```bash
   cd backend
   python scripts/run_free_image_canary.py --place-ids id-1,id-2
   ```

3. Execute with the exact confirmation count:

   ```bash
   python scripts/run_free_image_canary.py \
     --place-ids id-1,id-2 \
     --run --confirm-count N
   ```

4. Verify every new row is hidden and non-primary.
5. Fetch and inspect each candidate. Reject logos, icons, text-only/menu images presented as food, duplicates, low-resolution assets, unrelated/stale media, or unproven rights.
6. Only a separate reviewed promotion change may make approved images public or primary.
7. Report attempted, candidates found, accepted after review, rejected, public promotions, and net coverage change.

Stop if Google is reachable, a candidate becomes public automatically, a target already has an image row, source ownership is unclear, or writes exceed the reviewed set.

### Phase F — widen only on evidence

A cohort may grow from 3–5 to 10, then 25, only when the prior cohort has zero contamination, complete provenance, no paid calls, acceptable source-level precision, stable service health, and deterministic quarantine/rollback IDs.

Do not enable recurring acquisition after one successful canary. First add a per-run cap, source allowlist, rate limit, cost guard, kill switch, idempotency proof, and rollback procedure. Submit scheduler expansion as a separate production/security PR for independent review.

## Success metrics

- 100% of canary targets are entity-verified before execution.
- 100% of written rows retain traceable provenance.
- 0 paid-provider calls in the free-source track.
- 0 unreviewed images become public or primary.
- 0 contaminated menus remain active after review.
- Report source-level precision and recall separately.

Always report absolute counts and percentages:

```text
menu:       before_count / active_places = before_pct
            after_count  / active_places = after_pct
            net +count, +percentage_points
public img: before_count / active_places = before_pct
            after_count  / active_places = after_pct
            net +count, +percentage_points
primary:    before_count / active_places = before_pct
            after_count  / active_places = after_pct
            net +count, +percentage_points
```

If the denominator changes, report it and provide a comparable-cohort calculation. Never extrapolate a small canary into a catalog-wide promise.

## Required deliverables

Use separate PRs for:

1. UI journey implementation and screenshots.
2. Read-only production baseline/evidence.
3. Each extractor fix or source adapter.
4. Each bounded canary evidence record.
5. Any promotion of reviewed images.
6. Any recurring-job expansion.

Every handoff must include branch, base SHA, commit SHA, diff scope, commands/results, production IDs touched, before/after counts, known gaps, rollback/quarantine status, and next action. Claude writes only `.agent-bridge/claude-to-codex.md`.

## Completion definition

This is complete only when:

- the first user journey is reviewable with current-build screenshots and test evidence;
- at least one free menu cohort and one free photo cohort have honest precision/recall evidence;
- production writes are exact-ID, bounded, attributable, reviewed, and reversible or quarantined;
- coverage movement is measured with reproducible before/after queries;
- recurring acquisition remains disabled unless it passes a later independent production-safety review.

If a source yields no safe gain, document why and move to the next source shape. Do not widen a failing method to manufacture a higher percentage.
