# Category taxonomy — design doc (2026-08-31)

Addresses Master Plan item E8. Per the plan's own 🔬 flag: this is a
design document, not code — the actual re-typing/schema change needs a
decision, not a guess, especially for the ownership/identity categories
(see "Needs a human call" below).

## Correction to the Master Plan's framing

The plan describes "32 flat categories mixing cuisine/meal-period/
dietary/experience/ownership" — checked the schema before writing
anything else, and that's only half right.

**Already exists**: `Category.type` (`app/db/models/category.py`) is a
real enum — `cuisine` / `venue` / `specialty` — set on every row at seed
time. This isn't a flat, undimensioned list at the schema level.

**What's actually still true**: that dimension is **completely invisible
end-to-end**. `CategoryOut` (`app/api/v1/schemas/categories.py`) exposes
only `id`/`name`/`icon`/`color` — no `type` field. `GET /categories`
therefore returns one flat list to the client, and grepping the whole
frontend for `CategoryType`/`category_type` turns up zero matches — the
Filter UI (`FilterSheet.tsx`) renders every category as siblings in one
list. So the user-facing complaint is accurate even though the backend
data model already has more structure than the plan assumed. The real
gap is "nothing surfaces or fully uses the dimension that's already
there," not "no dimension exists."

**Also true, narrower than "32 flat categories" suggests**: the
`specialty` type itself is a real grab-bag. Its 11 members mix at least
four distinct concepts:

| Category | Actual dimension |
|---|---|
| `halal`, `vegan`, `gluten_free` | dietary restriction |
| `family_owned`, `black_owned`, `woman_owned` | ownership / identity |
| `michelin_rated` | prestige / recognition |
| `late_night`, `romantic`, `kid_friendly`, `local_favorite` | occasion / vibe |

`cuisine` (15 members) and `venue` (5 members) are, by contrast, already
reasonably coherent — `bbq`/`seafood`/`pizza`/`coffee`/`desserts` read as
food-focus rather than strict national cuisine, but that's how every
directory app in this space (Yelp included) already treats this bucket
in its user-facing filter, not a real defect worth disrupting.
`breakfast` is arguably a meal-period rather than a cuisine, but it's a
single miscategorized row, not a structural problem — lower priority
than the `specialty` split below.

## Proposed model

No new table, no relationship change needed — `place_categories` is
already a proper many-to-many join (a place can carry multiple
categories simultaneously), and the fix is scoped to `Category.type`
alone:

1. **Extend `CategoryType`** with `dietary`, `ownership`, `occasion`
   (keep `cuisine`, `venue`; retire `specialty` once its members are
   redistributed — or keep it as a landing zone for genuinely
   miscellaneous future additions like `michelin_rated`, which doesn't
   cleanly fit anywhere else and arguably isn't a browsable category at
   all — see below).
2. **Re-type the 11 `specialty` rows** into the buckets in the table
   above. Pure `UPDATE categories SET type = ... WHERE slug = ...` —
   no migration of `Place` or `place_categories` rows, since category
   identity (`id`, derived from `slug`) never changes.
3. **Add `type` to `CategoryOut`** and `CategoriesResponse` — additive,
   doesn't break any existing consumer.
4. **Group the Filter UI by type** instead of one flat list — this is
   the actual user-facing payoff, and the part with real UX judgment
   calls (see next section).

Steps 1-3 are mechanical and low-risk (an additive schema change, a data
UPDATE, an additive API field) — buildable now without a product
decision, if you want me to build them next. Step 4 is where this needs
you.

## Needs a human call

**Grouping/labeling `family_owned` / `black_owned` / `woman_owned`
together as "ownership."** These three are functionally similar
(business-ownership attributes) but two of them are identity categories
in a way `family_owned` isn't, and how they're framed in a user-facing
filter section (a section literally labeled "Ownership"? Folded into a
broader "Values" or "Community" grouping? Kept as individual toggle
chips rather than grouped under any visible header at all?) is a real
representation choice, not an engineering one. This is exactly the kind
of thing this doc's own standard says shouldn't be decided unilaterally
— flagging it rather than picking an answer.

**`michelin_rated` as a "category" at all.** A place doesn't choose to
be Michelin-rated the way it chooses to be `vegan` or `late_night` — this
is an external recognition/award, closer to a badge or a sort signal
than a filterable identity tag. Worth deciding whether it stays a
`Category` row (simplest, no schema impact) or becomes a distinct
`Place`-level attribute instead (more correct semantically, but a bigger
change touching `Place`, not just `Category`) — not something to decide
by default via the taxonomy fix alone.

**How much to group the Filter UI at all.** Three concrete options, in
increasing order of disruption:
- **A — Sectioned single sheet**: same `FilterSheet`, but categories
  render under type-labeled headers ("Cuisine", "Dietary", "Occasion",
  "Ownership") instead of one flat grid. Smallest change, no new
  navigation, no new screen.
- **B — Faceted filters**: each type becomes its own filter facet
  (separate from category entirely) — e.g. a distinct "Dietary" chip row
  next to price-tier/distance, matching how price-tier already gets its
  own dedicated UI rather than living inside the category grid. Bigger
  change, more consistent with how the app already treats other filter
  dimensions.
- **C — Leave the flat list, use `type` only for analytics/ranking** —
  no visible UX change at all yet; use the now-exposed dimension
  internally (e.g. weighting an occasion match differently from a
  cuisine match in ranking) before touching the filter UI. Lowest risk,
  defers the UX call entirely.

No recommendation forced here — this is the tradeoff layout the plan's
own rule asks for, not a decision made on your behalf.

## Sequencing

If you want steps 1-3 built now: safe, mechanical, fully testable
without production access (an enum extension + a data UPDATE + an
additive schema field), same risk profile as the other schema-adjacent
fixes already shipped this session. Say the word and I'll build and PR
it. Step 4 (whichever option, if any) needs your call first.
