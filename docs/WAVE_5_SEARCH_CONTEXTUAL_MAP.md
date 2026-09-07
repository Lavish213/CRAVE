# Wave 5 — Search and Contextual Map

## Shipped in this change

- A deterministic, conservative query interpreter separates place/cuisine
  lookup text from price, dietary, and occasion/location language.
- Supported dietary categories are SQL-level hard filters. Unsupported
  allergy claims fail closed with an explicit explanation; the app does not
  imply allergy safety from category data.
- Interpreted constraints are visible and removable. Price is the only soft
  constraint and is relaxed only after zero results, never when an explicit
  filter control supplied the price.
- Results start at 12 and expand in bounded 12-result steps to 60.
- Exact-name matches bypass the list only after an explicit Search submit.
- Signed-in users can narrow the bounded candidate pool to Craves or Ranked.
- Search hands the displayed candidate array, its order, scope, query, and
  search-session ID directly to Map.
- Map renders that array without a second search or rerank, preserves Search
  attribution, fits it after the native map is ready, and clearly labels the
  active Search context.
- Panning does not silently replace pins. A new viewport fetch happens only
  after the user presses **Search this area**.
- With no location and no selected city, Map asks the user to choose an area
  instead of silently falling back to Oakland.

## Deliberately not fabricated

The contract names three personalized labels: **Best match for you**,
**Safer pick**, and **Worth exploring**. Current Search is relevance,
city-standing, and proximity ranked; it is not yet personalized to the signed-
in user's taste graph. It also has no evidence that makes "safer" a defensible
food-safety claim. Those labels are therefore not emitted by this change.

Before they can ship, the product owner must define whether "Safer pick" means
high-confidence recommendation quality (rename recommended) or dietary/allergy
safety (unsupported by the current data). **Best match for you** must remain
gated until a real user-specific score participates in Search ordering.

## Verification boundary

Repository tests prove interpretation, hard filtering, bounded pagination,
explicit exact-match navigation, Search-to-Map parity, explicit map refresh,
location fallback behavior, and parent Search attribution. Native visual and
gesture quality still requires the normal device-review gate before merge.
