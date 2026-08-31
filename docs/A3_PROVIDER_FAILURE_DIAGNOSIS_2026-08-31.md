# A3 Square/Toast provider failure diagnosis

Date: 2026-08-31  
Mode: read-only production diagnosis plus local regression fixes  
Production mutations: none

## Outcome

The two historical `MenuSource` rows did not fail between claim emission and
canonical publication. Neither source has ever emitted a `PlaceClaim`,
`PlaceTruth`, or `MenuItem` row. Their old `last_success_at` values therefore
recorded extraction-layer activity rather than a published menu. PR #68
already corrected that success-accounting order for future runs.

The current public sources are still not publishable:

- **Itani Ramen / Toast** returns no real menu items through the free extraction
  route. Toast's normal response is a Cloudflare 403; the existing TLS
  impersonation fallback can fetch the public document, but its embedded JSON
  contains only generic business metadata under the current page shape. A
  permissive recursive adapter previously converted `{"name": "Itani Ramen"}`
  into one fake menu item. The two-item canonical gate prevented publication.
- **Reem's California - Mission / Square** is a public Square/Weebly site. It
  contains a benign feature flag named
  `ecom-checkout-cloudflare-challenge-recovery`; two independent block checks
  falsely treated that string as a bot challenge. Once allowed through, the
  public Square catalog returns one event ticket (`8.30 Sunday Supper ...`),
  not a restaurant menu. The two-item gate again correctly prevents
  publication.

This task fixes both confirmed false-positive behaviors, but it intentionally
does **not** manufacture a menu or mark either source successful. Retrying them
in production before this change is reviewed, merged, and deployed is out of
scope.

## Production evidence

Read-only queries were run against Railway's `CRAVE` service configuration.
No credentials or full environment output were printed or recorded.

### Itani Ramen

- Place ID: `a8ef634d-237d-5947-89b6-50c67bd245e9`
- MenuSource ID: `529bc5ab-d725-447b-bdbf-a45f8edba300`
- Provider: `toast`
- Source active: yes
- Historical `last_success_at`: 2026-08-27 17:14 UTC
- PlaceClaims: 0
- PlaceTruth rows: 0
- MenuItems: 0
- Current read-only extraction: 0 raw / 0 valid items

### Reem's California - Mission

- Place ID: `0325010a-1212-5ee4-b3b6-b37f7d5f6dda`
- MenuSource ID: `8d605752-4c0c-4fea-a7d2-ed1f2b8b08c8`
- Provider: `square`
- Source active: yes
- Historical `last_success_at`: 2026-08-09 UTC
- PlaceClaims: 0
- PlaceTruth rows: 0
- MenuItems: 0
- Current read-only extraction after the block fix: 1 raw / 1 valid product,
  an $85 event ticket rather than a menu item set

## Confirmed defects and fixes

1. `detect_hydration_state()` accepted the highest-scoring JSON payload even
   when every candidate scored zero menu signals. It now returns no hydration
   state unless the selected payload has a positive menu-shape score, including
   a bounded recursive check for legitimate nested Next.js/Apollo-style state.
2. `block_classifier.py` classified any HTML containing the word
   `cloudflare` as blocked. It now requires a challenge-specific marker.
3. `http_fetcher.py` independently repeated the same generic Cloudflare token
   check. It now uses the same challenge-specific signal class while retaining
   CAPTCHA, access-denied, and real Cloudflare challenge detection.

The challenge-specific signals include current Turnstile and managed-challenge
paths (`cf-turnstile` and `/cdn-cgi/challenge-platform/`) as well as the older
markers observed in the live Toast response.

Regression coverage proves benign Square feature flags pass both validation
layers, real Cloudflare challenge pages remain blocked, and zero-signal JSON
cannot become menu hydration.

## Safety conclusions

- The existing minimum-two-item gates in the orchestrator, claim emitter, and
  writer prevented both a one-row false menu and a one-product event catalog
  from reaching users.
- There is no orphan canonical state to repair for either source.
- These source rows should remain unmodified until a reviewed change is
  deployed. A future retry must be bounded and its claims/items verified before
  any success is asserted.
- Toast browser escalation was unavailable in the local probe because the
  Playwright Chromium binary is not installed locally. That is a verification
  limitation, not evidence that a deployed browser worker would find a menu.

## Verification commands

Focused regression and neighboring extraction tests:

```text
TZ=UTC PYTHONPATH=$PWD pytest -q \
  tests/test_a3_provider_regressions.py \
  tests/test_menu_extraction_observability.py \
  tests/test_menu_extraction_heuristics.py
```

Result after CodeRabbit follow-up coverage: `32 passed`.

Full backend result: `918 passed, 3 skipped, 32 warnings in 8.89s`.
