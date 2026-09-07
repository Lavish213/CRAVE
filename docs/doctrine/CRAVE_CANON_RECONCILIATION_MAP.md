# CRAVE Canon Reconciliation Map

**Status:** Adopted reconciliation pass (2026-09-07)
**Purpose:** Reconcile the existing intelligence-engine doctrine
(`CRAVE_MASTER_PRODUCT_INTELLIGENCE_BIBLE.md`,
`CRAVE_DECISION_INTELLIGENCE_ARCHITECTURE.md`,
`CRAVE_PLACE_DETAIL_SPEC.md`) against the product-decision set produced
by a full-product design interview conducted 2026-09-06/07 (Feed,
Decision Session, Discovery, Craves, Rank, Place Detail, Social/Posting,
Search, Map — recorded conversationally, not yet in a repo artifact).

This document does not replace any of the three existing doctrine
files. It is the traceable map between what they say and what has since
been explicitly decided, so a fourth competing canon document never
gets written and nobody has to guess which of two conflicting rules is
current.

**This is a documentation reconciliation only.** No application code
changes are authorized or implied by anything in this file. Where a
verdict below eventually requires a code change (e.g. a UI label), that
change is a separate, later, explicitly-scoped piece of work — not a
consequence of this document existing.

---

## 1. Governing rule

> Existing doctrine remains the authoritative intelligence-engine
> foundation. Later, explicitly approved product decisions supersede
> conflicting older product/UI decisions. Superseded rules remain
> traceable with their replacement decision and date; they do not
> coexist as competing canon.

Practically: nothing below deletes text from the existing doctrine
files. A follow-up pass (tracked separately, not part of this document)
annotates each superseded section in place with a pointer to this map,
so a reader landing on the old section is redirected rather than misled.

---

## 2. Adopted refinement (applies before the reconciliation table)

`CRAVE_DECISION_INTELLIGENCE_ARCHITECTURE.md` §23–24 draws a distinction
the interview's own conclusions did not make precisely enough:

> Retrieval/history surfaces may still show factual history even when
> an interaction is excluded from recommendation influence.
> Recommendation memory and factual history are not necessarily the
> same view.

**This supersedes the interview's flatter framing** ("correction/
deletion must propagate through derived intelligence," stated
repeatedly across the Rank, Craves, Posting, and Taste Profile
sections). The existing doctrine's two-operation version is more
correct and is now canonical everywhere the interview used the blunter
version:

- **Correcting recommendation influence** ("don't use this to learn
  from me," a Taste Profile correction, a retracted post's evidence
  weight) removes the item's effect on derived taste/ranking. It does
  **not** require deleting the underlying factual record.
- **Deleting user data** (account deletion, a deleted post, a withdrawn
  save) removes the underlying record itself, subject to whatever
  retention/legal lifecycle applies to that data type.

Every reconciliation-table entry and every future artifact that touches
correction, deletion, or "what CRAVE remembers" should use this
two-operation model, not the single blunt one.

---

## 3. Reconciliation table

| # | Existing canon | Current decision | Verdict | Authoritative destination |
|---|---|---|---|---|
| 1 | Bible §22–26, §37 — five screens are **Feed / Map / Search / Craves / You**; Map is a top-level tab; ranking lives inside "You," no standalone Rank tab. | Interview Section 1 — five screens are **Feed / Search / Craves / Rank / Profile**; Map is contextual-entry only; Rank is first-class because it's the explicit taste-teaching engine, not a sub-panel of Profile. | **SUPERSEDE** (navigation structure only — §22–26's *content* about what Feed/Search/Craves do, and §23's Map principles, still hold; only the tab assignment changes) | Future Route/Screen Registry artifact. Bible §22–26/§37 get an inline pointer to this entry once the canon-annotation pass runs. |
| 2 | Bible §13, Decision Architecture §4/§14/§18/§26/§28 — role trio named **"Best Tonight / Safe Bet / Wildcard."** Shipped backend (`decision_session_builder.py`, live) uses API value `"best_fit"`. Interview used "Best Fit." | Keep API identifier `best_fit` unchanged (already shipped — no backend churn). User-facing/doctrine label becomes **Best Fit**. Canonical trio: **Best Fit / Safe Bet / Wildcard**. | **KEEP** (API) + **SUPERSEDE** (doctrine/UI text only) | Product Doctrine's recommendation-vocabulary section. Every "Best Tonight" occurrence in Bible/Decision Architecture is a text-only edit in the later canon-annotation pass — not a code change. |
| 3 | Bible §18, Decision Architecture §22 — cold-start calibration list includes price preference and travel willingness as things to directly calibrate at onboarding. | Interview cold-start section — price sensitivity and travel willingness are purely behaviorally inferred, never asked directly (self-report is unreliable for both). Direct-ask stays narrowly scoped to: dietary/allergy hard constraints, a starting novelty-dial position, 3–5 known-restaurant lightweight reactions, and optional coarse cuisine-affinity taps. | **SUPERSEDE**, narrowly — only the price/travel-willingness calibration items. The rest of §18/§22 (food comparisons, cuisine/dish winners, ranking known restaurants, "don't make calibration feel like paperwork") is unaffected and still canonical. | Future Cold-Start/Onboarding spec, with the narrowed list stated explicitly so the scope of the supersede doesn't get read as broader than it is. |
| 4 | Place Detail Spec §3.2/§6 — Decision Strip explicitly omits open/closed status because `Place` has no `hours`/`is_open` field; logged as a real, tracked ingestion gap. | Interview Q8 — operational status belongs in the Decision Strip as a product requirement. | **KEEP** (the Spec's current honest-omission behavior was already correct) + **EXTEND** (state the general principle explicitly: required product behavior and current data readiness are different claims — missing data changes what CRAVE can honestly show, not what the product is ultimately supposed to show). No supersede needed; nothing here actually conflicted. | Product Doctrine gets the general principle. Place Detail Spec §6 remains the specific tracked instance (hours/is_open ingestion) and needs no edit. |
| 5 | Place Detail Spec §3.8 + §8 item 10 — "Seen on social" (imported social-link content, Bible §20) has no assigned home; already flagged as an open question needing explicit sign-off before implementation. | Interview Section 10 defined native CRAVE posting (structured, restaurant→dish→media→reaction) in full, but never addressed imported social-link content, which is a different evidence class with different provenance/trust characteristics. | **OPEN** — stays open. Explicitly must not be silently merged with the native-posting model just because both are "social content" on Place Detail. | Tracked here and in Place Detail Spec §8 until a deliberate decision is made. No implementation may assign it a permanent surface until then. |

---

## 4. Carried-forward open items (not new conflicts — restated here for one traceable list)

| Item | Status | Where it was raised |
|---|---|---|
| Visible social Rank (exact position / tier-only / favorites-only / nothing unless shared) | **OPEN** | Interview, Rank section — a real fork in what Rank *is*, deliberately not resolved unilaterally. |
| Taste-similarity person recommendations ("follow this person," vs. using the same signal invisibly for content relevance) | **OPEN** | Interview, Social Graph section — using similarity to rank content is locked/safe; using it to grow the social graph is a different, riskier mechanic requiring explicit approval. |
| Standalone Leaderboard (breadth/activity framing vs. Rank's preference-ordering leaderboard) | **AUDIT REQUIRED** — not approved, not rejected | Interview, App Structure section — burden of proof is on Leaderboard surviving contact with the actual current screen inventory without duplicating Rank or rewarding volume/competition. |

---

## 5. What this document deliberately does not do

- It does not edit Bible/Decision Architecture/Place Detail Spec in
  place. A separate, later pass adds inline "superseded — see
  reconciliation map" pointers at the specific sections named in the
  table above.
- It does not create the Route/Screen Registry, Cold-Start spec, or
  updated Product Doctrine referenced in the "authoritative
  destination" column — those are the next artifacts in the agreed
  sequence (Product Doctrine → V1 Scope → Route/Screen Registry → Flow
  Map → Data/State Model → Privacy/Permission Matrix → Evidence/Signal
  Hierarchy → Component/Design System → screen contracts).
- It does not touch `frontend/` or `app/` code. The `best_fit` API
  value ships unchanged; only doctrine text and eventual UI copy are
  affected by entry #2, and that UI-copy change is separate, later,
  explicitly-scoped work.
