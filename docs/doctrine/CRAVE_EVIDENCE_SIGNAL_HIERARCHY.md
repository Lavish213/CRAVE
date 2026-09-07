# CRAVE Evidence / Signal Hierarchy

**Status:** Canonical scope artifact (2026-09-07)
**Purpose:** Given data CRAVE is allowed to possess (per
`CRAVE_PRIVACY_PERMISSION_MATRIX.md`), exactly how much is each signal
allowed to influence taste, context, confidence, ranking, and future
recommendations? This is a formalization of the existing intelligence
doctrine's own scoring architecture, not a second one.

**Authority hierarchy:** existing doctrine → reconciliation map →
annotated supersessions → V1 Scope → Target Screen Registry → Route &
Flow Map → Data & State Map → Privacy/Permission Matrix → this
document.

---

## 1. This is a formalization, not a second architecture

`CRAVE_DECISION_INTELLIGENCE_ARCHITECTURE.md` already defines the load-
bearing structure this document builds on:

- **§6 User Intelligence Model** — Layer A (Explicit Preferences,
  highest authority: allergies, dietary restrictions, explicit
  likes/dislikes, "less of this," "do not learn from this"), Layer B
  (Long-Term Taste, derived), Layer C (Recent Behavior), Layer D (Taste
  Modes/Journeys), Layer E (Current Decision Context, ephemeral).
- **§7 Signal Interpretation** — Weak (impression, brief detail view) <
  Moderate (save, meaningful exploration) < Strong (selected for the
  meal, directions, reservation/order, confirmed visit) < Very strong
  ("definitely would get again," repeated dish selection, "more like
  this"). Negative signals already have semantic mappings here ("Too
  far" → travel tolerance, not cuisine affinity; "Too expensive" →
  price tolerance, not dislike; "Had this recently" → temporary
  suppression, not taste; "Not craving it" → context-only, little/no
  long-term penalty; "Don't like this" → real persistent negative).
- **§23 User Control** — More of this / Less of this / Not tonight /
  This wasn't for me / Don't learn from this / Remove preference /
  Reset inferred preference.
- **§30 Production Invariants** — several already state exactly what
  this document formalizes (temporary intent cannot silently become
  permanent taste; dish and restaurant preference remain independently
  representable; etc.).

Bible §5.2's ordered list (Impression → Click → Long detail view →
Repeated search → Save → Directions/selection → Confirmed visit/order
→ Post-visit ranking → Would-get-again → Repeat visit) and
`CRAVE_DATA_STATE_MAP.md` §4-§5 (visit evidence tiers, the immutable-
event/two-operation correction model) are the other two direct
ancestors of everything below. This document's job is to name the 21
concrete signal classes CRAVE actually produces, place each precisely
within that existing layer/tier structure, and make the resulting
precedence and decay rules explicit enough that neither Codex nor a
future model can misread them.

| This document's tier | Decision Architecture mapping |
|---|---|
| 0. Safety/hard constraint | Layer A, pre-ranking hard filter (§9) |
| 1. Explicit correction & control | Layer A |
| 2. Rank | Layer B, "very strong" tier, but scoped as its own precedence level per locked rule (§3 below) |
| 3. Verified/declared structured behavior | Layer B/C, "strong" tier |
| 4. Weaker explicit behavior | Layer B/C, "moderate" tier |
| 5. Inferred behavior | Layer C, "weak-moderate," requires reinforcement |
| 6. Passive behavior | Layer E / "weak" tier |

---

## 2. Locked rules — impossible to misinterpret

1. Explicit correction outranks behavioral inference.
2. Hard constraints outrank recommendation scoring and are never
   relaxed silently.
3. Rank is the strongest ordinary preference signal, but it cannot
   override a hard constraint.
4. A verified/declared visit proves experience, not necessarily
   preference.
5. An inferred visit alone does not unlock Rank eligibility.
6. Save means interest, not love.
7. Search means intent/context and only weak taste evidence unless
   reinforced by a subsequent action.
8. A rejection must preserve its reason. "Too far," "too expensive,"
   "not tonight," and "not for me" are not equivalent.
9. "Not for me" is negative preference evidence but not a bottom Rank
   tier.
10. Silence/non-action is weak or no evidence, never confident dislike.
11. Dish affinity and restaurant affinity remain separate.
12. Social evidence may support discovery but cannot become popularity
    scoring.
13. Commercial/compensated evidence has zero recommendation influence.
14. Deleted/retracted evidence must stop influencing derived
    intelligence.
15. Factual history and recommendation influence remain independently
    controllable.
16. Recent/session intent must not silently rewrite long-term taste.

Every signal row in §3 is a specific instance of one or more of these.

---

## 3. Signal classes

Each entry: Source · Explicit/inferred · Positive/negative/neutral ·
Relative strength · Confidence requirements · Decay behavior · Context
specificity · Restaurant vs. dish scope · Long-term taste effect ·
Recent/session intent · Recommendation confidence effect · Eligibility/
filtering role · Factual history · May be overridden by · Correction/
deletion behavior.

### Tier 0 — Safety/hard constraint

**1. Dietary/hard-constraint declaration**
Source: explicit declaration (onboarding, Taste Profile/Settings) ·
Explicit/inferred: explicit · Valence: neutral — a constraint, not a
preference vote · Strength: absolute, outranks all recommendation
scoring (locked rule #2) · Confidence req.: none beyond the user's own
statement · Decay: none, persists until changed · Context specificity:
applies universally, not session-scoped · Restaurant/dish scope: both
· Long-term taste: n/a — a filter, not a taste signal · Recent/session
intent: cannot be overridden by session intent · Recommendation
confidence: gates eligibility before confidence is even computed ·
Eligibility/filtering: hard filter, applied before ranking (Decision
Architecture §9) · Factual history: n/a, a standing rule · Overridden
by: nothing, ever · Correction/deletion: user edits directly, effective
immediately.

### Tier 1 — Explicit correction & control

**2. Explicit Taste Profile correction**
Source: Not true / Doesn't matter to me / Less of this / More of this ·
Explicit/inferred: explicit · Valence: whichever direction stated ·
Strength: Layer A, outranks all derived/behavioral evidence (locked
rule #1) · Confidence req.: none, explicit statements are always
trusted · Decay: holds indefinitely; re-examined (not silently
overridden) only if repeatedly contradicted by strong behavior — see §5
· Context specificity: trait- or context-specific per how applied ·
Restaurant/dish scope: whichever the corrected trait concerned ·
Long-term taste: yes, directly edits the derived model · Recent/session
intent: durable, not session-scoped · Recommendation confidence: raises
confidence in the corrected direction · Eligibility/filtering: only a
hard filter if the corrected trait was itself constraint-like ·
Factual history: the correction event is retained; does not delete the
behavioral events it corrects for · Overridden by: a later explicit
correction, or surfaced as an honest conflict against strong repeated
behavior, never silently · Correction/deletion: is itself a correction
mechanism; a specific correction can be reverted to fall back to
inference.

**3. Novelty control**
Source: onboarding starting position, adjustable in Taste Profile/Feed
· Explicit/inferred: explicit · Valence: neutral, a tuning parameter ·
Strength: Layer-A-adjacent, governs Wildcard's aggressiveness and
hole-in-the-wall pacing · Confidence req.: none · Decay: durable
setting persists until changed; an optional session override ("feeling
adventurous today") never silently rewrites the durable setting ·
Context specificity: durable + optional session-level, tracked
separately · Restaurant/dish scope: restaurant/candidate level · Long-
term taste: sets exploration tolerance, not itself a cuisine/dish
preference · Recent/session intent: session override doesn't persist ·
Recommendation confidence: modulates Wildcard's exploration radius ·
Eligibility/filtering: not a filter, a weighting parameter · Factual
history: n/a · Overridden by: only explicit user adjustment ·
Correction/deletion: user adjusts directly any time.

### Tier 2 — Rank

**4. Rank comparison**
Source: Rank Comparison outcome (win/loss/tie/insufficient-data) ·
Explicit/inferred: explicit, a deliberate comparative judgment ·
Valence: relative — a win/loss between two known places, not an
absolute rating · Strength: **the strongest ordinary preference
signal**, but cannot override a hard constraint (locked rule #3) ·
Confidence req.: requires declared/verified visits to both compared
places · Decay: the outcome itself never expires as a fact; only its
weight in "recent form" modeling decays (Data & State Map §5) · Context
specificity: can be cuisine/context-scoped as evidence supports (the
original hierarchical Rank design) · Restaurant/dish scope:
restaurant-level in V1 (dish Rank deferred, V1 Scope §3.6a) · Long-term
taste: yes, directly and strongly · Recent/session intent: recent
comparisons weighted more heavily for current form without erasing
older ones · Recommendation confidence: raises confidence significantly
· Eligibility/filtering: not a filter, a strength signal · Factual
history: permanent regardless of later influence corrections ·
Overridden by: only an explicit Taste Profile correction or a hard
constraint — never by a weaker behavioral signal · Correction/deletion:
user can delete a specific rank entry; cascades per Data & State Map §5.

### Tier 3 — Verified/declared structured behavior

**5. Verified visit**
Source: Rank action itself, or a tagged native post with corroborating
media (Data & State Map §4) · Explicit/inferred: verified tier,
stronger than declared · Valence: neutral — proves experience occurred,
not a preference direction · Strength: high, but strictly evidentiary/
eligibility-granting (locked rule #4) · Confidence req.: the
corroborating action/media is the confidence source · Decay: does not
decay as a fact; recency is a separate, decaying signal · Context
specificity: n/a · Restaurant/dish scope: restaurant-level (dish-level
if the tagged post named a dish) · Long-term taste: **no, by itself** —
only becomes a taste signal once paired with a reaction (#4 Rank, #8
structured meal reaction) · Recent/session intent: n/a · Recommendation
confidence: unlocks Rank-comparison-eligibility · Eligibility/
filtering: gates Rank-queue entry · Factual history: permanent ·
Overridden by: n/a, it's a fact · Correction/deletion: user can delete
the record; standard propagation.

**6. Declared visit**
Source: explicit "I went," or a confirmed location-inference prompt ·
Explicit/inferred: explicit by definition · Valence: neutral, same
proves-experience-only rule as verified · Strength: same eligibility
tier as verified for Rank-queue purposes (both sufficient per Data &
State Map §4) · Confidence req.: the explicit statement, or a confirmed
inference · Decay: does not decay as a fact · Context specificity: n/a
· Restaurant/dish scope: restaurant-level · Long-term taste: no, by
itself, same rule as verified · Recent/session intent: n/a ·
Recommendation confidence: unlocks Rank-comparison-eligibility ·
Eligibility/filtering: gates Rank-queue entry · Factual history:
permanent · Overridden by: n/a · Correction/deletion: user can delete;
standard propagation.

**7. Structured meal reaction (Loved it / Good / Not for me)**
Source: post-visit prompt, Native Posting composer or standalone log ·
Explicit/inferred: explicit · Valence: whichever the user selects — the
first genuinely preference-bearing signal a visit can carry · Strength:
strong, a deliberate structured statement, feeding toward but distinct
from a full Rank comparison · Confidence req.: requires an associated
declared/verified visit — cannot exist standalone · Decay: persists as
factual history; contributes to recent-form weighting · Context
specificity: tied to the visit's captured context (who, occasion) if
any · Restaurant/dish scope: restaurant-level by default, dish-level if
tagged · Long-term taste: yes, moderately — weaker than a full Rank
comparison (no comparative judgment), stronger than a save ·
Recent/session intent: contributes to recent-interest modeling ·
Recommendation confidence: raises confidence moderately · Eligibility/
filtering: nudges toward a full Rank comparison later ("want to teach
CRAVE more? Rank it") · Factual history: permanent · Overridden by: a
later full Rank comparison for the same place, or an explicit
correction · Correction/deletion: editable/deletable, standard
propagation.

**8. Reservation/order evidence**
Source: a completed reservation/order via a deep-link provider ·
Explicit/inferred: explicit action, verified-tier visit corroboration ·
Valence: neutral — proves commitment/intent-to-visit, not preference ·
Strength: strong as visit-corroborating evidence; **zero influence from
the commercial relationship itself on ranking** · Confidence req.: the
completed transaction · Decay: n/a as a fact; contributes to visit-
evidence freshness · Context specificity: n/a · Restaurant/dish scope:
restaurant-level · Long-term taste: only indirectly, via the visit
record it corroborates · Recent/session intent: n/a · Recommendation
confidence: corroborates visit-evidence confidence only · Eligibility/
filtering: contributes verified-tier evidence toward Rank eligibility ·
Factual history: permanent · Overridden by: n/a · Correction/deletion:
standard propagation.

### Tier 4 — Weaker explicit behavior

**9. Save/Crave**
Source: Save action · Explicit/inferred: explicit action, weak
preference signal · Valence: positive, but weak — **Save means
interest, not love** (locked rule #6) · Strength: moderate-weak, above
passive/inferred tiers, below any visit-based signal · Confidence req.:
none beyond the action · Decay: decays in weight if untouched over
time, never force-deleted · Context specificity: n/a · Restaurant/dish
scope: restaurant-level, or dish-level if a specific dish was saved ·
Long-term taste: weak — nudges category interest without declaring a
strong preference · Recent/session intent: n/a · Recommendation
confidence: minor positive nudge only · Eligibility/filtering: not a
filter · Factual history: persists until removed · Overridden by:
easily, by any stronger signal · Correction/deletion: user removes
directly; present/absent, not graded, so no separate correction
mechanism is needed.

**10. Rejection with reason**
Source: Decision Session "Not for me"/reject, with an optional reason
chip · Explicit/inferred: explicit · Valence: negative, but **the
reason changes what it means** — see §4 Negative Evidence Semantics ·
Strength: moderate, reason-dependent · Confidence req.: none beyond the
action · Decay: contextual reasons (too far, too expensive, not
tonight) decay fast/session-scoped; a genuine preference rejection
persists longer · Context specificity: high, the entire point of
preserving the reason · Restaurant/dish scope: whichever the rejected
card concerned · Long-term taste: only a genuine preference-rejection
reason affects it; contextual/operational reasons affect only
context/travel/price tolerance, never cuisine affinity (reusing
Decision Architecture §7's mapping directly) · Recent/session intent:
contextual reasons are session-scoped by nature · Recommendation
confidence: lowers confidence in the rejected direction, scoped to the
reason · Eligibility/filtering: "too far"/"too expensive" adjust
soft-constraint tolerance, never hard-filter · Factual history: the
rejection event persists; its influence is independently correctable ·
Overridden by: a later positive signal for the same category once the
contextual reason no longer applies · Correction/deletion: standard
propagation.

**11. Private log**
Source: F6.4, private-visibility path · Explicit/inferred: explicit ·
Valence: whichever reaction was attached, if any · Strength: identical
to its underlying components (visit tier + reaction) — **private
logging is a visibility choice, not a distinct evidence type** ·
Confidence req.: same as underlying · Decay: same as underlying ·
Context specificity: same as underlying · Restaurant/dish scope: same
as underlying · Long-term taste: same as whatever reaction/visit
evidence it carries · Recent/session intent: same as underlying ·
Recommendation confidence: **identical to the same evidence posted
publicly** — visibility never changes recommendation weight ·
Eligibility/filtering: n/a · Factual history: permanent until deleted ·
Overridden by: same as underlying evidence type · Correction/deletion:
standard propagation.

**12. Explicit Search modifiers**
Source: typed/selected constraint chips (cuisine, price, distance,
"from my Craves," etc.) · Explicit/inferred: explicit · Valence:
neutral-to-weak-positive, momentary intent not durable preference ·
Strength: weak-moderate, and **only becomes real taste evidence once
followed by an action on a result** (locked rule #7) · Confidence req.:
none for the modifier itself · Decay: session-scoped, discarded at
session end unless it produced a follow-on action · Context
specificity: high, tied to that search session's intent · Restaurant/
dish scope: whichever the query targeted · Long-term taste: none
directly, only via a resulting save/visit/rank · Recent/session intent:
this *is* recent/session intent by definition — must never silently
rewrite long-term taste on its own (locked rule #16) · Recommendation
confidence: n/a directly · Eligibility/filtering: acts as a soft (or
hard, if dietary) constraint for that search only · Factual history:
the search event is retained for zero-state UI; evidence weight is
separate · Overridden by: expires naturally each session · Correction/
deletion: user can clear search history.

### Tier 5 — Inferred behavior

**13. Inferred visit**
Source: bare location proximity, unconfirmed · Explicit/inferred:
inferred · Valence: neutral · Strength: lowest of the three visit
tiers — **insufficient alone to unlock Rank-comparison-eligibility**
(locked rule #5) · Confidence req.: below the Rank-eligibility
threshold; sufficient only to trigger a confirmation prompt · Decay: if
unconfirmed, does not persist as a visit record at all — simply expires
· Context specificity: n/a · Restaurant/dish scope: restaurant-level ·
Long-term taste: no · Recent/session intent: n/a · Recommendation
confidence: none until confirmed (promoted to declared) · Eligibility/
filtering: does not gate Rank-queue entry; sufficient for Craves
graduation only (a separate, lower-stakes case) · Factual history: none
persisted unless confirmed · Overridden by: confirming promotes it to
declared; ignoring it discards it · Correction/deletion: n/a, nothing
persisted to correct/delete unless confirmed.

**14. Search behavior (raw query, pre-action)**
Source: the query itself, before any click/save/rank on a result ·
Explicit/inferred: explicit query, inferred-strength evidence ·
Valence: neutral until acted on · Strength: the weakest form of
"explicit" input in this hierarchy, grouped with inferred-tier signals
for evidentiary purposes · Confidence req.: none — a query alone proves
nothing · Decay: ages out of "recent searches," no lasting evidence
weight · Context specificity: session-scoped · Restaurant/dish scope:
whichever was searched · Long-term taste: **none, ever, from the query
alone** (locked rule #7) · Recent/session intent: yes, exactly what it
represents · Recommendation confidence: n/a · Eligibility/filtering:
n/a · Factual history: retained for UI purposes (recent searches), not
as taste evidence · Overridden by: n/a, it was never a taste claim ·
Correction/deletion: user can clear history.

**15. Post/caption evidence**
Source: free-text caption on a native post · Explicit/inferred:
explicit text, excluded from structured evidence status · Valence:
whatever sentiment the text implies — never parsed as structured
evidence · Strength: **zero as a taste signal** — never Rank order,
always weighted below structured reactions · Confidence req.: n/a,
never trusted as structured evidence regardless of content · Decay:
n/a · Context specificity: n/a · Restaurant/dish scope: n/a · Long-term
taste: none, ever · Recent/session intent: none · Recommendation
confidence: none · Eligibility/filtering: none · Factual history: the
text persists as part of the post · Overridden by: n/a, never a taste
claim · Correction/deletion: editable/deletable with the post.

### Cross-cutting scope modifiers

**16. Dish evidence**
Source: saves/reactions/posts/menu ingestion scoped to a dish id (Data
& State Map §8) · Explicit/inferred: inherits from the parent signal
type · Valence: inherits · Strength: **this row is a scope modifier,
not an independent tier** — dish evidence uses the exact same strength
rules as its parent signal type, scoped to a dish id · Confidence req.:
inherits · Decay: inherits · Context specificity: inherits, and is
independent of the parent restaurant's own affinity (locked rule #11,
Decision Architecture §2.4) · Restaurant/dish scope: **is** the
distinction this row exists to enforce · Long-term taste: inherits, but
tracked as a separate dish-level affinity, never merged with restaurant
-level · Recent/session intent: inherits · Recommendation confidence:
inherits · Eligibility/filtering: inherits; explicitly excludes
dish-level Rank (V1 Scope §3.6a) · Factual history: inherits ·
Overridden by: inherits · Correction/deletion: inherits — retracting the
source event retracts the dish evidence it contributed.

**17. Social evidence**
Source: followed-user activity, native posts from others, the
similarity-weighted social rail · Explicit/inferred: inherits from the
underlying event, plus a derived similarity-weighting layer · Valence:
support-only — never an independent positive/negative vote of its own
(locked rule #12) · Strength: may support discovery presentation and
content-ranking weighting; **may never become a popularity score or
independently drive a place's recommendation confidence** · Confidence
req.: n/a as its own category · Decay: n/a as its own category,
inherits from the underlying post/reaction · Context specificity: n/a ·
Restaurant/dish scope: whichever the underlying content concerns ·
Long-term taste: **no** — informs which content surfaces to a user, it
never directly edits that user's own taste graph the way their own
Rank/Save/visit does · Recent/session intent: n/a · Recommendation
confidence: contributes to content *relevance* ranking in the social
rail only, never to a place's own fit/confidence score · Eligibility/
filtering: n/a · Factual history: n/a as its own category · Overridden
by: n/a · Correction/deletion: the mute / "don't use this person's
taste" controls (Privacy Matrix §3 F1) govern this independently of the
underlying content's own lifecycle.

### Firewalled — zero recommendation influence

**18. Commercial/affiliated evidence**
Source: sponsored, comped, or employee-affiliated content ·
Explicit/inferred / Valence: n/a · Strength: **zero, always, no
exceptions** — this is the firewall (locked rule #13) · Confidence
req.: n/a · Decay: n/a · Context specificity: n/a · Restaurant/dish
scope: n/a · Long-term taste: **none, ever, regardless of surface
confidence, engagement, or business relationship** · Recent/session
intent: none · Recommendation confidence: excluded entirely from any
place/dish's fit or confidence computation · Eligibility/filtering: n/a
· Factual history: the content itself persists, properly disclosed,
just never counted as evidence · Overridden by: cannot be "promoted"
into real evidence by any volume, engagement, or payment · Correction/
deletion: standard content lifecycle, `source_type` immutable.

### Meta-operation

**19. Deletion/retraction**
Source: any explicit user deletion action · Explicit/inferred:
explicit, but this is a meta-operation on other signals, not itself a
preference signal · Valence: n/a · Strength: n/a — it doesn't carry a
strength, it removes another signal's influence · Confidence req.: n/a
· Decay: n/a, takes effect immediately · Context specificity: n/a ·
Restaurant/dish scope: whichever the deleted evidence concerned ·
Long-term taste: removes the deleted item's contribution to derived
taste immediately; does not retroactively fabricate a different history
· Recent/session intent: n/a · Recommendation confidence: recomputation
must reflect the retraction, logged as an auditable event (Data & State
Map §5/§11, Route & Flow Map F13.2) · Eligibility/filtering: n/a ·
Factual history: **this is the one operation that actually removes
factual history** — distinct from a correction, which only flips
influence (locked rule #15) · Overridden by: n/a, it is itself the
final word on that piece of evidence · Correction/deletion: is the
operation.

*(Two signal classes from the requested list are folded into rows
above rather than given separate entries, since they aren't distinct
evidence types: **Place Detail engagement** is the same as the passive/
weak tier of behavioral evidence, covered under §3's Tier 6 as its own
named row for completeness — see below — and every field applies the
same way an impression does, just slightly stronger.)*

### Tier 6 — Passive behavior

**20. Passive exposure/impression**
Source: a candidate shown without further engagement · Explicit/
inferred: inferred, weakest tier · Valence: neutral — **silence/non-
action is weak or no evidence, never confident dislike** (locked rule
#10) · Strength: weakest, proves almost nothing alone · Confidence
req.: none · Decay: essentially immediate; repeated impressions without
engagement inform repetition suppression (Decision Architecture §12),
not a dislike signal · Context specificity: n/a · Restaurant/dish
scope: whichever was shown · Long-term taste: none · Recent/session
intent: none · Recommendation confidence: none directly, feeds only
position-bias/repetition-suppression bookkeeping · Eligibility/
filtering: none · Factual history: logged for ledger auditability
(position-bias guard), not as taste evidence · Overridden by:
trivially, by any actual action · Correction/deletion: n/a, not
user-facing evidence to correct.

**21. Place Detail engagement (dwell/detail view)**
Source: opening/viewing Place Detail without a further action ·
Explicit/inferred: inferred · Valence: weak-positive at most · Strength:
weak-moderate, above a bare impression, below Save · Confidence req.:
none · Decay: fast — a single detail view is easily outweighed, doesn't
accumulate meaningfully alone · Context specificity: n/a · Restaurant/
dish scope: restaurant-level (dish-level if a specific dish section was
engaged with) · Long-term taste: minimal, easily overridden · Recent/
session intent: contributes weakly to session-level interest ·
Recommendation confidence: minor · Eligibility/filtering: none ·
Factual history: logged, low evidentiary weight · Overridden by:
trivially · Correction/deletion: n/a as a distinct correctable item, not
surfaced to the user as discrete evidence.

---

## 4. Negative evidence semantics

The single easiest place to destroy the taste model. Six distinct
categories, never conflated:

1. **Preference rejection** — a genuine "I don't want this kind of
   thing" signal: "Not for me" with no contextual reason, or a repeated
   pattern of rejecting a category with no operational excuse. Affects
   long-term taste. Not a bottom Rank tier (locked rule #9) — it's
   excluded from the ordering entirely, a different fact than "worst
   liked place."
2. **Contextual rejection** — "not tonight," "not in the mood." Session
   -scoped, little-to-no long-term penalty (Decision Architecture §7's
   existing "Not craving it" mapping).
3. **Operational rejection** — "too far," "too expensive," "been there"
   recently. Updates travel/price/repetition tolerance specifically,
   never cuisine/category affinity (Decision Architecture §7's
   existing "Too far"/"Too expensive" mappings, directly reused).
4. **Constraint conflict** — a candidate that violates or nearly
   violates a hard constraint that should have been filtered upstream.
   This should be rare (hard filters run before presentation, §9 Tier
   0) — when it surfaces, it is a data-quality/filtering-failure signal
   to log and fix, never a taste signal to learn from.
5. **Repetition/fatigue** — "had this recently." Temporary suppression,
   not a taste judgment — distinguishes "I dislike ramen" from "I love
   ramen but had it three times this week" (Decision Architecture §12).
6. **Uncertainty** — "too close to call," "haven't been to one of
   these" (Rank Comparison's own honest outcomes). Not negative at all
   — a confidence/data-quality statement, never fabricated into a
   preference in either direction.

---

## 5. Conflict-resolution precedence

Reconciled against — not substituted for — Decision Architecture's own
Layer A/B/C/D/E structure and weak/moderate/strong/very-strong tiers
(§1's mapping table). The result:

```
1. Safety / hard constraint           (Tier 0 — §3.1)
2. Explicit correction & control      (Tier 1 — §3.2, §3.3)
3. Rank                               (Tier 2 — §3.4)
4. Verified/declared structured       (Tier 3 — §3.5-§3.8)
   behavior
5. Weaker explicit behavior           (Tier 4 — §3.9-§3.12)
6. Inferred behavior                  (Tier 5 — §3.13-§3.15)
7. Passive behavior                   (Tier 6 — §3.20-§3.21)
```

This holds up against existing doctrine precisely because it *is*
existing doctrine, made explicit: level 1 is Decision Architecture's
hard-filter stage (§9); levels 2-3 are Layer A explicit preferences,
which the existing architecture already places above Layer B derived
taste — Rank sits just below explicit correction because a correction
is a direct statement about what the model should do, while Rank is
still (extremely strong) derived behavioral evidence; levels 4-7 are
Decision Architecture §7's weak/moderate/strong/very-strong ladder,
unchanged.

**One caveat, not an exception to the ordering:** when an explicit
correction and *repeated, strong* Rank behavior genuinely disagree over
time, the correct response is not to silently let level 2 always beat
level 3 — it is to **surface the conflict honestly** to the user
("you said you don't care about spicy food, but you keep ranking spicy
places highly — still true?"), per the already-locked Taste Profile
correction behavior. The precedence table governs which signal wins
*in a single scoring computation*; it does not license ignoring a
standing, repeated contradiction in the input data.

---

## 6. Decay and persistence semantics

Semantic classes only — no numeric half-lives locked here, since
existing architecture doesn't yet support calibrating them and
inventing precise decay curves ahead of real usage data would be
exactly the "complexity the system hasn't earned" pattern already
banned (Bible §3 principle 11).

- **Never decays until corrected** — hard constraints (§3.1), explicit
  corrections (§3.2), novelty's durable setting (§3.3), Rank comparisons
  as facts (§3.4), all declared/verified visit records (§3.5-§3.6) as
  facts.
- **Slow decay (long-term taste layer)** — Save/Crave weight (§3.9),
  dish/restaurant affinity accumulated from repeated behavior (§3.16).
- **Fast/session decay** — session-scoped Search modifiers (§3.12),
  contextual/operational rejection reasons (§4.2/§4.3), novelty's
  session override (§3.3), passive impressions (§3.20).
- **Immediate expiry unless confirmed** — an inferred visit that is
  never confirmed (§3.13) simply never becomes a persisted record.
- **Suppression, not decay** — repetition/fatigue signals (§4.5)
  temporarily suppress a category/dish; they do not decay an affinity
  score, because there is no affinity change to begin with.

---

## 7. Evidence contamination firewall

- **Sponsored/commercial evidence** (§3.18) — zero recommendation
  influence, no exceptions, cannot be earned by volume or payment.
- **Popularity/social virality** — never a ranking input at any layer;
  social evidence (§3.17) may only weight content *relevance* within
  the social rail, never a place's fit/confidence score.
- **Restaurant-submitted content** — factual-only (Data & State Map
  §6, Privacy Matrix G2), never treated as taste evidence regardless of
  how it's phrased or how often it's updated.
- **Imported external social content** — kept in its own
  `imported_external` bucket (Data & State Map §7), never blended with
  native evidence; its Place Detail placement remains explicitly OPEN
  (Route & Flow Map §1.1/§5.1a) regardless of how this firewall is
  implemented.
- **Manipulated/deleted posts** — evidence must retract immediately
  upon moderation removal, exactly as it would on user-initiated
  deletion (Route & Flow Map F13.2) — a moderator's removal and a
  user's own deletion have identical downstream effect.
- **Uncertain provenance** — anything without a clear source/confidence
  stamp must never be silently treated as high-confidence evidence; it
  inherits the same honesty-over-fabrication rule that governs stale
  operational data (Data & State Map §6).

---

## 8. Codex Evidence Invariants

Codex may **transport, render, collect, or invoke** the evidence
semantics approved in this document. Codex may **not**:

1. Invent new evidence weights or strength tiers not named in §3.
2. Collapse two distinct signal classes into one (e.g., treating a
   Save the same as a Rank comparison, or a contextual rejection the
   same as a preference rejection).
3. Reinterpret negative evidence — the six categories in §4 are not
   suggestions; a rejection's stated reason must be preserved and
   applied per its category, never averaged into a generic "dislike."
4. Convert engagement into preference — an impression, a dwell, or a
   caption does not become taste evidence no matter how it's phrased in
   a later feature.
5. Widen any signal's recommendation influence, decay class, or
   eligibility role beyond what §3 states, without an approved,
   traceable canonical change — the same process every other
   supersession in this project has followed.
6. Let Rank, or any other signal, override a hard constraint under any
   circumstance (locked rule #3).

---

## 9. Next artifact

Per the sequence, the next canonical artifact is the **Design System**
— typography scale, spacing/radius/elevation rules, photography
treatment, Decision Strip grammar, cards/sheets/buttons/chips, tier
presentation, states, motion/haptics, and accessibility. This document
locked how strongly each allowed signal may influence CRAVE; the Design
System locks how that intelligence is allowed to look before the
Component Registry and individual Screen Contracts freeze anything
visual.
