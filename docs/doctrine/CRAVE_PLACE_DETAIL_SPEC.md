# CRAVE Place Detail — Redesign Spec

**Status:** Approved for implementation
**Scores against:** `CRAVE_MASTER_PRODUCT_INTELLIGENCE_BIBLE.md` §33
(Master Brutal Screen Rubric), governed by §30-32 (visual doctrine /
anti-slop list / originality test) — no separate constitution needed,
those sections already function as one.
**Baseline audit:** current implementation scores 57/100 against §33
(see `CRAVE_STATE_OF_THE_APP.md` §3 and the session that produced this
spec) — sits at the boundary between "functional but weak" and
"rework." The engineering underneath (accessibility labels, haptics,
race-safe fetch effects, offline-safe save) is genuinely solid; the
information architecture is what's failing. This spec targets 85+.

---

## 1. Product question this screen must answer

Every other CRAVE screen answers "what should I eat" in the abstract.
Place Detail is the one screen that has to answer, concretely:

> **Why should I choose THIS place?**

Nothing on the current screen answers that question directly — it
presents facts (name, category, price, a rank CTA, a menu) and expects
the user to synthesize the decision themselves. This spec's entire
point is to do that synthesis for them, honestly, using only signals
CRAVE actually has today.

---

## 2. The one hard rule this spec exists to enforce

**Never fabricate personalization.** The anti-slop list (§31) already
bans "fake personalization based on one click" and "arbitrary
percentages presented as intelligence." CRAVE currently has **no user
taste graph** (Decision Intelligence doctrine's Gate 2 — explicit
preferences, derived taste profile, recent-behavior representation —
has not been built). That means a "94% match" / "you rank Thai highly"
style section, however good it looks in a mockup, would be lying to the
user about what CRAVE actually knows. This spec is written against
what's real today, with an explicit, marked upgrade path for when Gate
2 lands — not against an imagined future data model.

**Also newly confirmed while writing this spec, and worth stating
plainly**: `Place` has no `hours`/`is_open`/`open_now` field at all —
"Open until 10 PM" cannot be shown honestly today. This is a real data
gap (hours were never ingested), not a UI decision. It's called out
below wherever it matters, with the honest fallback for now and what
building it for real would require.

---

## 3. Information hierarchy, section by section

### 3.1 Hero
Unchanged in substance, reordered in emphasis. Full-bleed image/video
gallery (already built — `ImageGallery`, `PlaceVideoGallery`), but the
**name comes before the tier badge**, not after — identity first,
judgment second. Current implementation has this backwards.

```
[ hero image/video gallery ]

Nari                          [CRAVE Pick]
Thai · $$$ · 1.8 mi
```

Distance is computable today (`useLocation` + `place.lat/lng`) and
should appear here — it currently doesn't appear on this screen at all
despite being available.

### 3.2 Decision strip
One glance, the facts that gate whether this is even viable right now.

```
[ 💰 $$$ ]  [ 📍 1.8 mi ]  [ 🔗 Directions ]
```

**Explicitly omit an open/closed indicator** until real hours data
exists — a fabricated or stale "open now" is worse than none (a wrong
"open" sends someone to a closed restaurant; that's a trust failure
the anti-slop list would call "misleading precision," §33 category J).
Log this as a real backend task (see §6) rather than faking it in the
UI layer.

### 3.3 "Why this fits" — the section that must stay honest
This is the section the doctrine's screen framing calls for and the
current screen has zero equivalent of. Content today, using only real
signals:

```
CRAVE Pick — top 5% in San Francisco

3 of your friends ranked this place.
Maya ranked it #4 in SF.

[ You ranked this 8.4/10 — tap to see your comparison ]  ← only if myRanking exists
```

What this is: the existing percentile tier (already real, already
correctly *not* personalization — labeled as a catalog fact, "top 5% in
San Francisco," never "94% match for you"), the real friend-ranking
count and names (`get_friend_rankings_for_place` — already built,
already used elsewhere on this screen, just not synthesized into a
single "why" block), and the user's own past ranking if one exists
(`myRanking` — already fetched on this screen).

What this is **not**, until Gate 2 taste-graph work actually lands:
any sentence implying CRAVE knows the user's personal cuisine
preference. No "you tend to like Thai." No match percentage. When that
data becomes real, this section gets a second line
(`"92% match — you rank Thai and spicy food highly"`), added as new
content, not as a cosmetic label on top of the same absence of data.

### 3.4 Primary action
Unchanged — already correct. The single prominent "I ate here" /
"Your score · tap to re-rank" CTA, visually distinct from every other
action, is the one piece of this screen already at doctrine standard.
Keep it exactly as-is, just move it up to directly follow §3.3 rather
than sitting below the badge row.

### 3.5 What to get
Menu content, promoted from "a collapsible list near the bottom" to a
visually prominent section — large cards for standout dishes, not a
plain text list. Uses the existing menu data (`getPlaceMenu`,
`MenuItem`) exactly as-is; no new backend work required for this part.

**Do not** imply dish-level recommendation intelligence
("recommended for you") — no dish-affinity model exists (Decision
Intelligence doctrine §10, not built). Show the menu, sized to draw
attention, without claiming CRAVE picked these dishes for the user
specifically.

### 3.6 Social proof
Replace the current scattered friend-ranking list with a single,
synthesized line already covered by §3.3's content — do not duplicate
it as a second section. If there's more signal than fits in §3.3 (e.g.
several friends, not just one named), a short expandable list belongs
here, but the headline claim lives in §3.3.

**Never** show a directory-style star average (`⭐ 4.7 (3,481)`) — the
anti-slop list bans "ratings copied from directory products without
strategic purpose," and CRAVE has no such aggregate to show honestly
anyway (ranking is comparison-based, not a star average).

### 3.7 Actions row
Unchanged in function, unchanged in position (immediately below the
primary CTA) — Save / Website / Order / Directions. Already correctly
built (accessibility labels, haptics, optimistic save). No redesign
needed here; this row already meets the bar.

### 3.8 Progressive disclosure (below the fold)
Full menu, photo/video galleries in full, hours (once real), full
details, report/moderation entry points. Exactly the current content,
just explicitly *after* everything above rather than interleaved with
it.

---

## 4. Anti-slop compliance check (§31)

Explicitly checked against every item that could plausibly apply to
this screen:
- No fabricated percentage/match score (item 10, 27) — see §2.
- No "For You" language without explainable personalization (item 7) —
  §3.3's copy is written to only ever claim what's actually backing it.
- No directory star ratings (item 25) — §3.6.
- No premature social proof (item 24) — friend-ranking count only shown
  when a real count exists (already true today: the section is empty
  when there are zero friend rankings, not padded with a fake claim).
- No unexplained badge (item 20) — the tier badge already carries a
  defined meaning (CRAVE Pick / Hidden Gem / Worth Knowing / Explore),
  kept.
- No decorative motion delaying the primary action (item 29) — the
  existing haptic-on-tap pattern stays; no new animation is introduced
  by this spec.

---

## 5. What this spec deliberately does not attempt

- Real-time open/closed status — genuine data gap, not a design
  decision. See §6.
- Dish-level personalized recommendation — no dish-affinity model
  exists (Gate 3, Decision Intelligence doctrine).
- A numeric taste-match score — no taste graph exists (Gate 2).
- Any new backend endpoint or schema change — every data point this
  spec uses is already fetched by the current screen
  (`fetchPlaceDetail`, `getPlaceMenu`, `fetchFriendRankings`,
  `fetchMyRankings`, `useLocation`). This is an information-architecture
  and visual redesign, not a new-feature build.

---

## 6. Real gaps this spec surfaces (log, don't block on)

- **Place hours/open-status is not modeled at all.** Worth a real
  ingestion task (a `hours` field + whatever source can populate it —
  Google Places already exposes this if that's part of the discovery
  pipeline) before the decision strip can honestly show open/closed.
  Track this in `CRAVE_STATE_OF_THE_APP.md`'s roadmap, not as part of
  this screen's implementation.

---

## 7. Acceptance criteria

- Re-score against §33 after implementation; target 85+ (currently 57).
  Category-by-category expectation:
  - A (product purpose): 9+ — the screen now visibly answers "why this
    place."
  - B (information hierarchy): 9+ — identity leads, decision-relevant
    content is front-loaded, everything else is progressive disclosure.
  - C (decision usefulness): 12+/15 — real signals synthesized into one
    "why" block instead of scattered facts.
  - D (originality): 8+ — the "why this fits" block plus the
    already-good rank CTA make this unmistakably CRAVE, not a directory
    template.
  - E (personalization): stays honest — do not inflate this score with
    fabricated signal; 5-6/10 is correct until Gate 2 lands, and that's
    fine.
  - F, G, H, I: should not regress from current (7, 8, 7, 3) — this is
    an IA/visual change, not a rebuild of the fetch/error/accessibility
    layer that's already solid.
  - J (trust/explainability): 4+/5 — the "why this fits" block is
    itself the explanation the current screen lacks.
  - K (retention): stays at 4+/5 — the re-rank affordance is unchanged.
- No new backend endpoint required to ship this (§5).
- Full frontend test suite + `tsc --noEmit` clean, same as every other
  change this session.

---

## 8. Forensic inventory — existing screen, section by section

Read directly from `frontend/app/place/[id].tsx` (858 lines) before any
code was touched, per the rule: inventory and grade first, rearrange
second. Every section of the current screen, mapped against the target
IA above.

| # | Existing section (current code) | Verdict | Target IA section | Reason | Backend field(s) used |
|---|---|---|---|---|---|
| 1 | Header share button (`navigation.setOptions`) | **Keep** | n/a (chrome, not body) | Already correct, not part of the IA reorder. | `place.name` (share text) |
| 2 | `ImageGallery` (hero images) | **Keep** | §3.1 Hero | Already built, already correct. | `place.images`, `place.image`, `place.image_gps_verified` |
| 3 | `PlaceVideoGallery` | **Keep** | §3.1 Hero | Self-contained, already correct; sits directly under photos. | `place.id` (self-fetches) |
| 4 | Identity block (`TierBadge`, price, name, category/address) | **Move** | §3.1 Hero | Order is backwards today — tier badge before name. Target: name first, tier badge second, **add distance** (currently absent from this screen despite being computable). | `place.name`, `place.category`, `place.address`, `price` (via `formatPrice`/`place.price`), `place.rank_percentile` (via `getTierForPlace`) — distance needs `useLocation()` + `place.lat`/`place.lng`, both already available, hook not currently used on this screen |
| 5 | Emoji badge chips (`getBadges`: tier star/gem, delivery/menu, "off the grid") | **Compress** | Tier chip → §3.1 identity line + restated in §3.3; delivery/menu chip → redundant with the Actions row's Order/Website buttons, candidate for **removal**; "off the grid" → folds into §3.2 Decision strip as an honest access-signal, not a separate row | Currently a flat 3-chip row with no hierarchy; the spec's sections already carry this information with more context (§3.1, §3.3, §3.7) so a bare chip row duplicates rather than adds. | `getTierForPlace(place)`, `place.has_menu`, `place.grubhub_url`, `place.website` |
| 6 | Primary rank CTA (`myRanking` score + tier dot, or "I ate here") | **Move** | §3.4 Primary action | Content and behavior already correct — just moved up to directly follow §3.3 "Why this fits" instead of sitting below the badge row. | `myRanking` (from `fetchMyRankings`), `place.id` |
| 7 | Action row (Save / Website / Order / Directions / Add photo / Add menu photo / Report) | **Keep** | §3.7 Actions row | Already at doctrine standard (accessibility labels, haptics, optimistic save, sign-in gating). No redesign. | `saved` (`isSaved`), `place.website`, `place.grubhub_url`, `place.lat`/`place.lng`, `place.image_ids` |
| 8 | Menu section (list, expand/collapse, verified-time, add/suggest button) | **Move** | §3.5 "What to get" | Same data, promoted from a collapsible list near the bottom to a visually prominent section with larger cards. No new fetch. | `getPlaceMenu(id)` → `menuItems`, `menuVerifiedAt`; `place.has_menu` |
| 9 | Friend rankings section (horizontal avatar/username/tier cards) | **Compress** | §3.3 "Why this fits" (headline), optional overflow in §3.6 Social proof | Spec explicitly folds this into the single synthesized "why" line rather than a standalone scroller; only an overflow list (more than the one or two names that fit inline) stays as its own element, and it lives in §3.6, not as today's always-separate section. | `fetchFriendRankings(id)` |
| 10 | "Seen on social" section (craves horizontal scroll, thumbnail + platform chip + author) | **Open question — not yet mapped** | none assigned yet | The spec (§3.1–3.8) never actually places this section. It's real signal (public UGC mentioning the place) but a different trust tier than friend rankings (§3.3) — lower confidence, no curation. Recommend §3.8 Progressive disclosure (below the primary decision content, above raw menu/photo detail) rather than inventing a new top-level section, but this needs an explicit call before implementation touches it. | `getCravesForPlace(id)` |
| 11 | `ReportPhotoSheet` modal | **Keep** | Entry point stays in Actions row (#7) / menu section (#8) | Unchanged trigger, unchanged content. | `place.image_ids[0]` |
| 12 | `MenuSubmissionSheet` modal | **Keep** | Entry point stays in §3.5 | Unchanged trigger, unchanged content. | `place.id` |
| 13 | `DetailSkeleton` / `ErrorState` | **Keep, but incomplete** | n/a (loading/error chrome) | Only two coarse states exist (full skeleton, hard error). See open states list below — several of the required states already work correctly under the hood but have never been explicitly designed as distinct visual states. | `isLoading`, `isError` from `useQuery` |

### Mechanics that must survive untouched (not part of the IA discussion — reorder around them, never rewrite them)

- The three stale-response generation-ref guards: `menuGenerationRef`,
  `cravesGenerationRef`, `friendRankingsGenerationRef`. Any section
  reorder must keep each fetch's effect wired to its own guard exactly
  as today.
- The upload-status effect's `moderationStatus`-vs-`status` separation
  (`'pending_review'` → "Submitted for review", `'rejected'` →
  "wasn't approved", else → "Photo added"; `'failed'` → toast + clear).

### Every state that must be explicitly designed (not just functionally handled)

Per-state design pass required before implementation is called done —
functioning correctly today is not the same as having a designed visual
state:

| State | Currently | Needs |
|---|---|---|
| Initial load | `DetailSkeleton` | Keep, restyle to match new hero-first layout |
| Partial data (e.g. no price, no address) | Silently omitted inline | Explicit — confirm every optional field has a real "not shown" behavior, not a blank gap |
| No images | `allImages` falls back to `place.image` or empty | Needs an explicit hero placeholder, not just an empty gallery |
| No menu | "No menu on file yet" text | Keep, restyle for the promoted §3.5 section |
| No friend rankings | Section conditionally hidden (`length > 0`) | Keep hidden; confirm §3.3 doesn't leave an awkward gap when it's the only signal missing |
| Unsaved / saved | `saved` boolean, optimistic + toast | Keep exactly |
| Upload pending review | Toast: "Submitted for review" | Keep exactly |
| Upload approved | Toast: "Photo added", `refetch()` | Keep exactly |
| Upload rejected | Toast: "wasn't approved" | Keep exactly |
| API error | `ErrorState` | Keep |
| Stale request cancellation | Generation-ref guards (silent) | Keep exactly, no visual state needed (silent by design) |

### Open questions this inventory surfaces (need a call before implementation)

1. **"Seen on social" (craves) has no assigned home in the target IA.**
   Recommend §3.8 Progressive disclosure; needs explicit sign-off since
   the spec didn't originally account for it.
2. **Delivery/menu emoji chip is likely pure duplication** of the
   Actions row's Order/Website buttons — recommend removing rather than
   compressing, but flagging rather than deciding unilaterally since
   it's a content-removal call, not just a reorder.
