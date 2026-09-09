# CRAVE UI V2 Semantic Contract

**Status:** UIV2-01 canonical presentation-semantics contract
**Purpose:** define what UI states mean before tokens/components render them. UI V2 components receive semantic props; screens do not choose colors or visual treatments ad hoc.

## 1. Governing rule

> UI V2 presentation may clarify meaning. It may not invent meaning.

Product truth continues to come from canonical CRAVE doctrine, screen/data/evidence contracts, and current validated behavior. A visual component translates that truth into presentation; it does not rerank a place, relax a constraint, fabricate an operational fact, or infer confidence the data model did not provide.

## 2. Recommendation confidence

`personalizationLearning` means **CRAVE has weak evidence about this user's taste in this context**.

It does **not** mean:

- the restaurant is bad;
- the restaurant has weak catalog quality;
- the restaurant is closed;
- the restaurant has poor reviews;
- the recommendation is unsafe.

UI wording should describe the uncertainty itself, e.g. `Still learning your taste here` only when the uncertainty is genuinely personalization-confidence uncertainty.

Concrete evidence gaps use concrete language instead:

- `Hours not recently verified`
- `Limited menu information`
- `Photo unavailable`
- `Few matching saves yet`

**Missing evidence is never rendered as negative evidence.**

## 3. Media semantics

`missingMedia` means no trustworthy image is available for this presentation.

It is a valid content state, not a loading error and not a broken card. The presentation becomes typography-led and must preserve identity, reasoning, operational facts, and actions without reserving a giant empty image box.

`failedMedia` means a known image source failed to render. UI may use the same visual fallback as missing media, but observability/test fixtures keep the underlying state distinct.

A poor-quality but valid real photo is not silently replaced with fake stock imagery.

## 4. Operational truth

Operational states are mutually distinct:

- `open` — current source supports open-now claim.
- `closed` — current source supports closed claim.
- `stale` — hours/status exist but freshness is insufficient for a current claim.
- `unknown` — no trustworthy operational status is available.

`stale` is **not** `closed`.

`unknown` is **not** `closed`.

No UI treatment may imply a live open/closed answer when the underlying data cannot support it.

## 5. Constraint semantics

### Hard/protected constraint

A dietary, allergy, religious, ethical, or user-promoted hard constraint is a **protected boundary**, not an ordinary preference filter.

It cannot be silently relaxed to produce results.

If CRAVE cannot verify the constraint safely, the UI must say so and may show zero results rather than fabricate compliance.

### Preferred/soft constraint

Price, distance/travel preference, context, cuisine affinity, novelty preference, or another user-soft preference may be candidates for explicit relaxation.

### Relaxation

A relaxation is a user-visible state transition. The interface must:

1. name exactly what would change;
2. preserve all hard/protected constraints;
3. require explicit user action when the requested constraint has not already been knowingly relaxed by the search contract;
4. never hide the fact that the result set changed because of the relaxation.

## 6. Search interpretation

Search interpretation explains what CRAVE understood from the user's query. It is not a chat transcript and should not ask a follow-up unless the product contract explicitly requires one.

When interpretation is uncertain, show an editable interpretation so the user can correct it.

Search reasoning vocabulary remains distinct from Decision Session reasoning vocabulary.

Search roles:

- `bestMatch`
- `saferPick`
- `worthExploring`

Decision Session roles:

- `bestFit`
- `safeBet`
- `wildcard`

Do not merge these into one generic enum merely because their presentation components share visual grammar.

## 7. Result ordering vs visual selection

A result's place in the ordered set is recommendation/search output.

A Map pin's `selected` state means **the user is currently inspecting that pin**.

Selection is not a new recommendation boost and never changes the candidate's ranking/evidence meaning.

Selected Map state must be visually distinguishable using more than color alone (shape/size/stroke/icon/label treatment as appropriate).

## 8. Map semantics

Map is spatial support for an existing bounded candidate set.

Search → Map uses the exact Search candidate set and does not independently rerank it.

Map direct/city mode may fetch a bounded nearby set, but the UI must not imply that tapping/panning itself changed recommendation quality.

Panning does not auto-refresh. `Search this area` is an explicit rerun.

Location denial/unavailability produces a manual `Choose area` path and list-equivalent access, never a dead end.

Social evidence never exposes or implies live user location.

## 9. Brand/accent semantics

The warm orange/gold UI V2 accent is reserved for:

- brand identity moments;
- the primary action;
- active/selected state when selection needs emphasis.

It is **not** the universal color for:

- positive/success;
- stale/uncertain;
- hard constraints;
- destructive/error;
- ordinary metadata;
- every icon;
- recommendation-role badges.

Decision Session and Search reason roles are text/structure-first and are not differentiated by a rainbow badge palette.

## 10. Semantic status roles

UI V2 exposes the following high-level presentation roles:

- `brand`
- `primaryAction`
- `selected`
- `positive`
- `uncertain`
- `destructive`
- `protectedConstraint`
- `neutral`
- `subtle`
- `disabled`

A component selects one of these based on product state. Screens do not pass arbitrary colors.

## 11. Save semantics

Save is a lightweight stateful action, not a full-screen success ceremony.

Successful save:

- updates state;
- shows toast/light inline confirmation;
- keeps the user in context;
- may expose `View in Craves` as a secondary follow-up.

A Save action does not imply visit, ranking, or endorsement.

## 12. Closed/changed place semantics

A closed place may remain visible where historical/saved context matters, but it must be unmistakably flagged and should not be presented as a currently actionable primary recommendation.

A changed/uncertain place state is not deleted merely because details are stale. The interface distinguishes factual uncertainty from negative taste.

## 13. Personalization vs catalog quality

CRAVE has multiple concept families that must remain visually and semantically distinct:

1. catalog percentile quality/tier;
2. personalized recommendation fit/confidence;
3. user's personal Rank tier;
4. operational status;
5. constraint safety.

No token/component may reuse one concept's semantic state as shorthand for another.

## 14. Recovery hierarchy

For Search/Map recovery:

- primary action: `See nearby options` when nearby options still respect all hard constraints;
- secondary action: `Edit search`;
- when a hard constraint would have to change, do not offer generic nearby options as if they were equivalent. Name the exact constraint change and require explicit action.

Recovery never silently broadens the search.

## 15. Evidence limitation

When a result is a strong intent match but CRAVE lacks enough personalized evidence, it may still appear with an explicit limitation.

Example semantic state:

`matchStrength="strong"`
`personalizationConfidence="learning"`
`evidenceLimitation="fewMatchingSaves"`

This means `strong intent match, taste-unverified`, not `poor recommendation`.

## 16. Content hierarchy

Food/appetite imagery may attract attention, but recommendation intelligence must remain legible without the image.

Search/Map order of comprehension:

**food → place → reason/evidence → operational truth → action**

The UI should recede behind photography where evidence supports photography. It should not become visually empty when photography is absent.

## 17. Accessibility semantics

Every meaning represented by color must also be available through text, iconography, shape, state labels, or accessibility properties.

All interactive UI V2 primitives target at least 44×44pt unless a platform/system-owned control governs its own target.

Text must support scaling/reflow without making the decision logic unreadable.

Reduced Motion changes presentation, not meaning or confirmation.

Map tasks must have list-equivalent access.

These are implementation requirements until runtime evidence exists; they are not pre-implementation verification claims.

## 18. Forbidden semantic shortcuts

UI V2 must never introduce:

- star averages/public Yelp-style review framing;
- fake fit percentages;
- popularity/trending as a raw recommendation reason;
- silent hard-constraint relaxation;
- stale hours presented as live status;
- missing evidence styled as dislike/negative quality;
- Map selected state presented as a higher recommendation rank;
- catalog-tier color reused for personal Rank tier meaning;
- engagement counts/comments/reposts as social prestige mechanics;
- a new recommendation vocabulary created only because a component needs a label.

## 19. Implementation API principle

Preferred:

```tsx
<ConfidenceStatement confidence="personalizationLearning" />
<OperationalStatus state="stale" />
<ConstraintToken kind="protected" />
```

Forbidden pattern:

```tsx
<Component borderColor="#F5A623" opacity={0.7} />
```

Components accept meaning. Tokens decide presentation.
