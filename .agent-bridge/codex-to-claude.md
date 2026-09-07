# H-20260907-search-map-master-iteration-2

Status: ready-for-review
Owner: Codex
Branch: codex/search-map-v15-master-iteration-2
Base SHA: c34a9dd7492f59918ee058fce615dfe17dba0f90
Commit SHA: 628b97f065295a297796b057d6b979e9ae52a56f
Allowed next files: docs/design/SEARCH_MAP_V15_MASTER_FRAMES_ITERATION_2.md, docs/design/search-map-v15-master-frames-iteration-2.svg, docs/design/search-map-v15-ramen-hero-v1.png

## Outcome

Created one focused exploratory Search/Map master-frame iteration without propagating it across the full state inventory. The board now demonstrates an original photographic hero and a visible typography fallback, moves recommendation reasoning into editorial copy, neutralizes interpretation chips so accent is reserved for answer/blocker moments, and replaces the generic map card with a dark asymmetric CRAVE answer surface.

## Verification

- `xmllint --noout docs/design/search-map-v15-master-frames-iteration-2.svg` -> passed with no output.
- `magick -background none search-map-v15-master-frames-iteration-2.svg /private/tmp/search-map-v15-master-frames-iteration-2-final.png` from `docs/design` -> rendered a 2200x1350 PNG; visually inspected all four frames and corrected explanatory-copy overflow.
- `identify docs/design/search-map-v15-ramen-hero-v1.png` -> 1536x1024 PNG.
- `rg` audit for exploratory/no-claim labeling, photo fallback, editorial reason, neutral interpretation labels, blocker treatment, and Map "Why here" content -> all required markers present.
- `git diff --check` -> passed with no output.

## Known gaps / risks

- Exploratory only: not Penpot-ready, componentized, threshold-approved, simulator-verified, or device-verified.
- Generated ramen photography is an original concept asset, not approved production restaurant imagery or a shipped-content sourcing policy.
- No state beyond the four master frames was propagated.

## Next action

Human/design visual audit of this four-frame iteration. If its component language is approved, separately scope propagation across the complete state package.
