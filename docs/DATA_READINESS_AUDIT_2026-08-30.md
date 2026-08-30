# Production data-readiness audit — 2026-08-30

All production queries in this audit were read-only. Counts are a snapshot,
not a promise that the database will remain unchanged.

## Executive verdict

- **Menu coverage is source-limited first, extractor-limited second.** Only
  985 of 37,761 active places have a menu (2.6%). Of the 36,776 without one,
  23,628 have no website, Grubhub URL, or menu-source URL, so no extractor can
  attempt them.
- **Provider extraction success was overstated.** Square and Toast each had a
  source marked successful but no canonical truth/menu rows. The orchestrator
  recorded success when a parser emitted candidates, before canonical
  validation and publication. This pass changes future success semantics to
  require public materialized rows.
- **Image classification is overwhelmingly unresolved.** 73,808 rows are
  explicitly `unknown`, 3,893 more have null `content_type`, and 72,226 of the
  unknown URLs are Google Places URLs. Re-running the existing positional
  heuristic cannot add semantic information and would skip already-non-null
  rows anyway.
- **Personalized ranking is not data-ready.** Production contains 324
  recommendation events from five sessions, only five outcome events, one
  signed-in user, and two rankings. Building a learned model now would fit one
  person's test behavior, not user preference.

## Menu evidence

### Whole active catalog

| Measure | Count |
| --- | ---: |
| Active places | 37,761 |
| With a materialized menu | 985 (2.6%) |
| Without a menu | 36,776 (97.4%) |
| Menu-less but has some source URL | 13,148 |
| Menu-less with no source URL | 23,628 |

Active discovered sources: 333 HTML, 71 Square, 43 hydration, and 10 Toast.
The two provider sources with `last_success_at` (Itani Ramen/Toast and Reem's
California/Square) had zero canonical menu items in their current truth.

### Oakland

| Measure | Count |
| --- | ---: |
| Active places | 5,921 |
| With a menu | 216 (3.6%) |
| Without a menu | 5,705 |
| No source URL | 5,384 |
| Has source, eligible now | 203 |
| Has source, in backoff | 118 |
| Has source, failed 4+ times | 293 |

The operational report previously issued one SQL query per sourced place and
could stall after printing only its heading. It now classifies backoff status
with one set-based query and reports source/materialized provider lineage.

### Legacy placeholder rows

Three active, zero-price, description-free rows match the publisher's exact
placeholder predicate:

- Hal's Office — `Test`
- Thyme to Eat — `test`
- Thyme to Eat — `Test2`

The new maintenance command defaults to preview, supports a transactionally
rolled-back simulation, and requires an exact confirmation sentinel to apply.
The production simulation found exactly those three rows and rolled back.
No apply was performed in this pass.

## Image evidence

| State | Count |
| --- | ---: |
| `unknown`, gallery-only | 59,649 |
| `unknown`, candidate-primary | 14,159 |
| null content type | 3,893 |

The existing Phase 3 backfill explicitly documents that opaque Google URLs are
classified by position, not image bytes. It intentionally assigns semantic
`unknown` while using Google's ordering as a quality proxy. A rerun therefore
cannot turn these rows into food/interior/menu/exterior labels.

The next useful image experiment is a bounded, cached, byte-based sample:

1. sample by URL host and current visibility, not random rows only;
2. fetch at most one normalized thumbnail per URL under existing network
   policy and cache by URL hash;
3. run the already-bundled TFLite classifier for food/non-food evidence;
4. compare against a manually labeled holdout before writing anything;
5. stage proposed classifications with model/version/confidence lineage;
6. promote only thresholds proven on the holdout, with rollback by batch.

This can be free in API terms, but it is not free of bandwidth/compute and must
respect source terms. It should not scrape around access controls.

## Ranking and product-data evidence

Recommendation-event totals: 324 events, five sessions, one signed-in user,
five outcome events (`click`, `save`, or `rank`). Surface volume is mostly
impressions: Feed 200, Map 90, Search 20, Decision Session 9. There are only two
place rankings across two places and one user.

Decision: keep deterministic rank/diversity logic. Do not train or tune a
personalization model until multiple real users produce enough outcomes for a
time-based offline evaluation with a holdout group.

The 32-category flat taxonomy remains a product-modeling problem, not a data
migration to improvise during population. Preserve current values until a
separate mapping proposal defines cuisine, service style, occasion, dietary,
and atmosphere dimensions with backward compatibility.

## Changes in this pass

- Optimized `menu_coverage_report.py` and added provider-lineage output.
- Corrected future `MenuSource.last_success_at` semantics: parsing candidates
  alone is insufficient; publication must produce at least one public row.
- Added guarded placeholder cleanup tooling and focused tests.
- Added a separate production classifier-status report.

## Remaining controlled actions

1. Review and merge this PR.
2. Independently review the three printed placeholder IDs; then run the exact
   apply command and verify all three are inactive (separate production act).
3. Run a small source-discovery/enrichment canary before attempting more menu
   extraction; the 23,628 source-less places are the largest coverage lever.
4. Investigate why the two historical Square/Toast candidate sets failed
   canonical publication before retrying them. Do not blindly rematerialize
   empty truth.
5. Design the bounded image holdout experiment above; do not rerun Phase 3 as
   if `unknown` were a transient processing failure.
