# CRAVE screen inventory + UX/design audit — 2026-09-06

## Purpose

Answers one question with evidence instead of impression: **are the
screens done?** Short answer — the product *logic* is mature enough for
release certification (this is what Phases 3-7 hardened: loading,
error, empty, permission, and destructive-action correctness). The
*visual identity* is not yet locked — this audit is the factual basis
for the screen-by-screen polish pass that comes next, ranked by
evidence rather than guesswork about which screens need it most.

This is a research/audit document — no code changed. It reads every
route in the app plus the shared components they render, and reports
concrete findings (quoted values, line-level behavior) against a
5-category framework: navigation/hierarchy, discovery cohesion, the
place-experience hub, state design, and visual identity.

## Screen inventory

Every route under `frontend/app/`, 20 files, grouped by function:

| Group | Screens |
|---|---|
| Discovery | `(tabs)/index.tsx` (Feed), `(tabs)/map.tsx` (+`map.web.tsx`), `(tabs)/search.tsx`, `(tabs)/craves.tsx` |
| Place | `place/[id].tsx` |
| Ranking | `rank/[placeId].tsx`, `leaderboard.tsx` |
| Identity | `(tabs)/profile.tsx`, `user/[id].tsx`, `taste-profile/[userId].tsx`, `profile-setup.tsx`, `settings.tsx` |
| Media | `record-video/[placeId].tsx` |
| Social/utility | `friends-feed.tsx`, `add-spot.tsx` |
| Legal | `legal/privacy.tsx`, `legal/terms.tsx` |
| Chrome/edge | `_layout.tsx`, `(tabs)/_layout.tsx`, `+not-found.tsx` |

Shared components reviewed: `PlaceCard`, `PlaceCardCompact`,
`EmptyState`, `ErrorState`, `SkeletonCard`, `TierBadge`,
`ComparisonChoice`, `Toast`, `SectionHeader`, `RankedPlaceRow`,
`MapBottomSheet`, `FilterSheet`, `AuthSheet`.

## Existing design foundation

The only shared design tokens in the app, all in
`frontend/src/constants/colors.ts`:

- **`Colors`** — background `#0A0A0A`, surface `#1A1A1A`, surfaceElevated
  `#252525`, border `#2A2A2A`, text `#FFFFFF`, textSecondary `#8C8C8C`
  (contrast-audit-driven value), textMuted `#555555` (deliberately
  sub-AA, disabled-only), semantic success/warning/error, 4 tier colors.
- **`Spacing`** — xs4/sm8/md12/lg16/xl24/xxl32.
- **`Radius`** — sm8/md12/card14/pill20/full9999.
- **`Shadows`** — card/control/floating/sheet tiers, added specifically
  because (per the file's own comment) cards were reading as "flat
  cutouts" with no elevation.

**No `Typography` scale exists anywhere.** Every screen and component
hand-types its own `fontSize`/`fontWeight`. Counting just the 13 shared
components: 13 distinct fontSize values (10-64) with no naming
convention — several are clearly meant to be the same role (a
"meta/caption" line is 11 in one component, 12 in another, 13 in a
third) and read as drift, not intentional variation. Individual
screens add their own local sets on top: Profile alone hand-types 13
distinct sizes, Place Detail 9, Settings 7 — none shared, none named.

## Cross-cutting findings, by the 5-category framework

### 1. Navigation + hierarchy

Strongest, most consistent category. Most screens have a genuinely
clear single primary action:

- Feed → tap a card → Place Detail.
- Place Detail's rank CTA is explicitly, deliberately the one
  prominent action (a code comment states this outright), with a
  disciplined primary/secondary/flat hierarchy below it.
- Rank's done-stage stacks filled → outlined → text-only buttons in
  clean descending weight.
- Map's bottom-sheet-then-tap funnel is explicit by comment: a bare pin
  tap is "engagement," the sheet's own tap is the real navigation.
- Leaderboard, Friends Feed, Search all have one obvious next step.

Two real exceptions:
- **Craves** has three independent lists under one scroll with no
  single dominant CTA — header share pill, per-row view, and per-row
  remove all compete at equal visual weight.
- **Feed's decision-session block** (when present) sits directly above
  the normal tiered feed as a second, differently-motivated "here's
  what to eat" prompt — two parallel entry points on one screen rather
  than one funnel.

### 2. Discovery experience cohesion (Feed/Map/Search/Craves/Rank)

Partially connected, not fully. Real sharing exists:
`PlaceCardCompact` is shared by Craves' Saves section and Search (both
trending and results rows), so those two screens' place-rows are
visually identical. `EmptyState`/`ErrorState` are shared across 8 and
10 screens respectively — a genuine, working design-system win.

But cohesion breaks in specific, nameable ways:
- **Two parallel tier-color systems**: `TierBadge`/`getTierForPlace`
  (from `utils/scoring`) vs. `RankedPlaceRow`'s `tierColor` (from
  `utils/rankScore`) — same concept, two separate implementations.
- **Two parallel ranked-row implementations**: `RankedPlaceRow` exists
  specifically for numbered/ranked rows with a score pill and is used
  on Profile/User — but **Leaderboard, the screen conceptually closest
  to it, reinvents its own row from scratch** instead of reusing it.
  Leaderboard's row happens to look like Craves' hand-rolled
  `craveRow` too, but only by copy-paste coincidence, not shared
  componentry.
- **`PlaceCard` and `PlaceCardCompact` duplicate, not share, logic**:
  both call the same derivation helpers in the same order
  (`getTierForPlace`, `formatPrice`, `getBadges`, distance, the a11y
  label formula) but each hand-types its own style sheet — and their
  "same role" text sizes don't even agree with each other (chipText 12
  vs. 11, percentile 12 vs. 11).
- **Map doesn't reuse `EmptyState`/`ErrorState`** at all — it hand-rolls
  its own banner-based equivalents (see Map section below); the
  *content* is real and designed, but it's a third implementation of
  a pattern the app already has two shared components for.

### 3. Place experience — is Place Detail the visual center?

Functionally, yes — more than a fact sheet: it genuinely aggregates
ranking, menu, saves/visited/notes, videos, friend rankings, and
"seen on social" UGC in one place, and every section has its own real
loading/error/empty handling rather than being stubbed.

Structurally, not yet a hub: it's a single linear `ScrollView` of
sequential sections (hero → video → identity → rank CTA → actions →
memory → menu → social) with **no in-page navigation** — no
section chips/tabs to jump to "Menu" or "Videos" directly, no
cross-linking between sections (tapping a friend's tier doesn't jump
to their own ranking of this place). It reads as "one long,
well-curated page containing all the right content," not yet as a
hub with parallel access to its parts. It's also the one screen
billed as the app's visual center that uses **zero `Shadows`
elevation** anywhere in its own stylesheet, by explicit design choice
("no boxed cards... typography carries the signal instead") — a
defensible individual choice, but one worth revisiting given the
elevation gap it creates against Feed's shadowed cards.

Two adjacent media sections on the same screen are also visibly
inconsistent: `ImageGallery`'s empty state is a real icon+text "No
photos yet"; `PlaceVideoGallery`'s no-thumbnail fallback is a flat,
unlabeled color box with no icon or text at all.

### 4. State design (loading / empty / error / permission / destructive)

This is where the app is genuinely strong, with a short list of real,
specific gaps — not a systemic problem.

**Strong, consistently real (not faked) across most screens:**
skeleton loading (Feed, Place Detail, Craves, Search, Leaderboard,
Profile, Friends Feed, User/Taste profile all use `SkeletonCard`
variants, not spinners), distinct empty-vs-error handling (several
screens explicitly document in comments that they *fixed* a prior bug
where errors were silently swallowed into an empty array — Leaderboard
and Friends Feed both), and a denied-vs-permanently-blocked permission
split implemented consistently across three different permission
types (camera/mic in `record-video`, location in `add-spot`,
notifications in `settings`) — routing to OS Settings only when
`canAskAgain === false`, never showing a dead "Allow Access" button.

**Specific, real gaps found:**
- **Map has no error/empty UI reuse** of the shared components (see
  above) — its own hand-rolled banners are real and do the job, but
  this was nearly missed because a shallower check (grep for shared
  component imports) reported "no error UI at all," which was wrong;
  worth noting as a caution for how this audit's own findings should
  be read — grep-for-import checks and full-file reads can disagree,
  and the full read is authoritative.
- **Rank's initial place-fetch loading is a bare spinner**, the one
  list-adjacent screen not using the skeleton pattern everything else
  uses.
- **Rank's top-level "retry" button doesn't actually retry** — it
  calls `router.back()`, a misleading affordance.
- **Rank's sign-in gate hand-rolls a near-duplicate of `EmptyState`**
  instead of using it.
- **`record-video`'s permission-hook-not-yet-resolved state renders a
  bare unstyled blank view** — no spinner, a real flash-of-nothing gap.
- **`record-video`'s failed `recordAsync()` call has no user-facing
  error** — silently resets state with only a `__DEV__` console
  warning, the one failure path in that file that doesn't toast,
  inconsistent with every other failure path in the same file.
- **Leaderboard has no distinct "sign in to see Friends board" state**
  — an unauthenticated user toggling to Friends likely falls through
  to the generic empty-board copy instead of a sign-in prompt, unlike
  Craves' explicit sign-in gate for the same underlying situation.
- **Craves' remove-a-save has no confirmation** — fires immediately on
  tap, only a toast after the fact (arguably fine given it's
  reversible, but worth a deliberate decision either way).
- **Account deletion's confirmation *mechanics* are solid** (two-step
  `Alert.alert`, explicit "cannot be undone," accurate scope
  description matching the privacy policy, non-silent failure
  handling that keeps the session alive to retry) **but its visual
  weight is not** — the "Delete Account" row uses the identical row
  template, size, and red tint as "Sign Out," with no danger-zone
  styling, heavier icon, or inline consequence summary distinguishing
  an irreversible data-destroying action from a reversible one until
  after it's already been tapped.

### 5. Visual identity

The single biggest lever available: **no Typography scale**, real
`Shadows`-adoption inconsistency, and a handful of small token-drift
instances (`add-spot.tsx` and `+not-found.tsx` both use literal `22`
where `Radius.pill` (20) exists; `PlaceCardCompact`'s `chip` uses a
literal `10` that matches no `Radius` value; `_layout.tsx`'s header
hardcodes `'#FFFFFF'` instead of `Colors.text` in the same file that
otherwise uses tokens).

`Shadows` in particular is defined, real, and genuinely under-used:
only `PlaceCard`, `PlaceCardCompact`, and `MapBottomSheet` use it.
Every hand-rolled row across Craves' secondary sections, Leaderboard,
Rank's tier/comparison cards, Profile's stat tiles, Settings' rows,
User/Taste Profile's cards, and Friends Feed's rows is a flat 1px
bordered box on `Colors.surface` — exactly the "flat cutout" problem
the token was created to fix, still present on most of the app.

Motion is real where it exists but concentrated in three places (Rank,
Map's `MapBottomSheet` drag physics, Feed's fade-in + `SkeletonCard`
shimmer) and absent almost everywhere else — Place Detail, Profile,
Settings, User Profile, Taste Profile, and Friends Feed have no
`Animated`/`Reanimated` motion of their own at all.

**Genericness, screen by screen**: Rank (the tiered comparison duel,
with an explicit code comment framing it as a deliberate Tinder-style
borrowing) and Search (its layered state machine) are the most
distinctive. **Settings and onboarding (`profile-setup.tsx`) are the
most generic** — Settings is structurally an unmodified icon+label+
chevron list indistinguishable from any other app's settings screen,
personality carried only by the header wordmark and footer line;
`profile-setup.tsx`, the very first screen a new user completes after
signing up, is a bare two-field form with no illustration or
onboarding "moment" despite otherwise-excellent inline validation UX.
**Leaderboard** is the most generic of the "list" screens — a stock
numbered-row-plus-toggle layout whose only distinctive touch is a
medal emoji. The legal pages and the tab bar/root layout are
correctly reskinned in the app's palette but are otherwise stock
patterns (a scrollable heading/bullet document; a default React
Navigation bottom tab bar with icon-swap-plus-color as its only
active-state treatment, no pill/background highlight).

## Per-screen findings, in priority order

*(Ordering follows the plan: Feed → Place Detail → Map → Craves/
Rankings → Profile/Settings → edge-state screens. Each entry is a
condensed pointer into the full findings above and the underlying
audit; specifics not repeated here are in the relevant section above.)*

**Feed** — Real skeleton/error/empty states, tiered structural idea
(Crave Pick/Gem/Solid/New sections), token-disciplined spacing, a real
perf choice (`FlashList`). Gaps: the decision-session block competes
with the main feed rather than integrating into it; no location-
permission UI (silently degrades); no in-file motion beyond a fade-in
(cards' own bounce/haptics live in `PlaceCard`).

**Place Detail** — See section 3 above. Strong information
architecture and a deliberate, well-reasoned button hierarchy; the
highest-value screen to invest in given the user's own framing of it
as the product's visual center, precisely because it's already close
functionally and the remaining gaps (hub navigation, elevation, the
video-gallery empty-state mismatch) are concrete and scoped.

**Map** — Best token discipline of any screen (correct `Spacing`/
`Radius`/`Shadows.control` usage throughout) and the richest custom
motion (hand-built drag-to-dismiss physics on `MapBottomSheet`, native
region animation). Real, designed error/empty banners that
distinguish "stale but shown" from "nothing shown" — just not built on
the shared `EmptyState`/`ErrorState` components. `map.web.tsx` is not
a degraded map but a full placeholder screen (native map libraries
can't bundle for web) — worth deciding if that's the permanent story
for CRAVE-on-web or purely incidental.

**Craves** — Three-source stitched list (native saves, social-matched
craves, manually-added) is a genuine structural idea undercut by two
visibly different row styles on one screen (shadowed `PlaceCardCompact`
rows vs. flat hand-rolled `craveRow`s). No confirmation on remove.

**Rank** — The single most distinctive, "moment"-driven screen in the
app (56pt score reveal, Tinder-style comparison duel, richest haptics/
motion) — the strongest evidence that CRAVE's uniqueness rule is
achievable, not aspirational. Held back by three small, fixable state
gaps: spinner instead of skeleton, a non-functional "retry" button, a
hand-duplicated sign-in gate.

**Leaderboard** — Solid state handling (skeleton, real error-retry,
scope-aware empty copy) wrapped around the most generic visual
presentation in the app; the clearest, lowest-risk "quick win" of the
whole audit — swap its hand-rolled row for the `RankedPlaceRow`
component that already exists for exactly this.

**Search** — Deepest and best state machine in the app (5+ distinct,
intentionally-designed states layered by query length/filters/
location); visual distinctiveness is entirely behavioral, not
structural — container is a standard search-bar-plus-list.

**Profile** — Strong partial-failure handling (independent per-section
fetch/error, so one failing endpoint doesn't blank the screen); real
personality via generated headline copy. No elevation anywhere on the
screen (flat stat tiles/rows).

**Settings** — Functionally correct (notification 4-state model,
two-step account-deletion confirmation with accurate, policy-matching
scope, non-silent failure handling) inside the most structurally
generic screen in the app. The one concrete, high-value fix: give
account deletion visual weight distinct from Sign Out before it's
tapped, not only inside the confirmation dialogs.

**User Profile / Taste Profile** — The most thoroughly state-audited
screens found (distinguishes 404 from transient error from blocked
from partial-relationship-fetch-failure, each with its own real UI);
Taste Profile has deliberate CRAVE-specific framing (percentile
reframed as "Top X%," explicit tier vocabulary). Both correctly guard
against account-switch/identity races.

**Profile-setup (onboarding)** — Excellent inline mechanics (debounced
live availability check, five distinct validation states, explicit
retry for a previously-real dead-end bug) inside the least visually
distinctive screen a new user sees — no illustration, no onboarding
moment, despite being literally the first screen after sign-up.

**Record-video (media capture)** — The one screen with a genuinely
different visual mode (full-bleed camera, floating chrome, a correct
circle-to-square record/stop metaphor). Best-in-class permission
handling. Two real gaps: an unstyled blank flash before permissions
resolve, and the one failure path (`recordAsync` throwing) with no
user-facing error, inconsistent with every other failure path in the
same file.

**Add-spot** — Consistent with the app's permission-handling
conventions (denied-vs-blocked split for location, same as
record-video/settings) but visually generic; some `Radius` token
drift (literal `22`/`18` instead of `Radius.pill`).

**Friends-feed** — Simple, correctly scoped (deliberately small and
chronological per its own comment), good state coverage, reuses the
shared tier-color logic for its score pills — one of the more
internally-consistent screens even without heavy investment.

**Legal pages** — Content is bespoke and accurate (names real vendors,
matches actual deletion scope); the visual template is a generic
scrollable heading/bullet document with no in-page navigation — low
priority to redesign, but a candidate for a shared "long-form legal
page" component if it isn't one already.

**+not-found** — A real, deliberate custom screen (explicit comment
citing the alternative: Expo Router's default off-brand fallback), but
visually minimal — same centered-icon-title-body-button skeleton as
every permission-denied state elsewhere.

**Root layout / tab bar** — Standard React Navigation chrome reskinned
via `screenOptions`/`Ionicons`, not a custom implementation. One
concrete inconsistency: the header's `headerTintColor: '#FFFFFF'` is a
hardcoded hex in the same file that otherwise threads `Colors` tokens
everywhere else. Tab bar's active-state treatment is icon-swap +
color only, no pill/background highlight — a candidate for a more
distinctive treatment if "every screen feels unmistakably CRAVE"
extends to the persistent chrome, not just screen content.

## What this means for the polish pass

Two kinds of work came out of this audit, and they should probably be
sequenced differently:

**Systemic (fix once, benefits every screen):**
1. A real `Typography` scale (named sizes/weights: display, title,
   body, caption, label) to replace ~15+ un-named hand-typed values.
2. An explicit decision on `Shadows` — adopt it everywhere flat cards
   currently exist, or deliberately keep Place Detail/Profile/Settings
   flat and document why (right now it reads as inconsistency, not
   choice).
3. Consolidate `PlaceCard`/`PlaceCardCompact`'s duplicated derivation
   logic into one shared hook/helper so their "same role" values can't
   drift again.
4. Retire one of the two ranked-row implementations (`RankedPlaceRow`
   vs. Leaderboard's/Craves' hand-rolled rows) in favor of a single
   ranked-row component with variants.
5. Sweep the small `Radius`/`Colors` token-drift instances found above
   (add-spot, +not-found, PlaceCardCompact, root `_layout.tsx`).

**Screen-specific (the actual polish pass, in the evidence-supported
priority order above):** Feed → Place Detail → Map → Craves/Rankings
→ Profile/Settings → edge-state screens. Place Detail is the highest-
leverage individual screen given the user's own framing of it as the
product's visual center and the concrete, scoped nature of its gaps
(hub navigation, elevation, the video/image gallery empty-state
mismatch). Leaderboard and onboarding are the cheapest wins (an
existing component swap; a first-impression moment currently missing
entirely). Settings' account-deletion row is the one item worth
treating as a standalone, fast, high-value fix regardless of when the
broader polish pass happens, given it's a real-money release-risk
item (destructive action, currently under-weighted visually) rather
than a pure aesthetics concern.
