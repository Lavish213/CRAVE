# CRAVE Rank Presentation Mapping

**Status:** GREEN — canonical implementation decision (2026-09-07)

## Purpose

Resolve the implementation boundary between the existing persisted personal-ranking model (`liked | fine | disliked`) and the approved Rank Home presentation tiers (`Elite | Love | Good`) without rewriting historical ranking evidence or changing the comparison algorithm.

## Canonical rule

The persisted ranking tier is an **evidence/algorithm bucket**. The Rank Home tier is a **derived presentation label**. They are intentionally not the same schema field.

The current backend score bands are:

- `liked`: 6.6–10.0
- `fine`: 3.3–6.6
- `disliked`: 0.0–3.3

Rank Home derives presentation tiers as follows:

| Persisted tier | Rank score | Rank Home presentation |
|---|---:|---|
| `liked` | `> 8.3` | **Elite** |
| `liked` | `<= 8.3` | **Love** |
| `fine` | any valid score | **Good** |
| `disliked` | any valid score | **Excluded from ordered Rank** |

`8.3` is the exact midpoint of the existing `liked` band (`(6.6 + 10.0) / 2`). This introduces no new weighting model and is deterministic from already-persisted data.

## Invariants

- Do not migrate or rewrite historical `PlaceRanking.tier` values for presentation purposes.
- Do not change comparison insertion behavior or score bands merely to produce Rank Home labels.
- `disliked` remains negative preference evidence and never becomes a bottom ordered Rank tier.
- Rank Home labels may change visually, but the underlying evidence must remain reconstructable and stable.
- Exact score and exact numbered position remain drill-down information, not default Rank Home presentation.
- This rule is presentation-only and must not change recommendation influence by itself.

## Traceability

Backward authority: `CRAVE_SCREEN_CONTRACT_RANK_HOME.md`, `CRAVE_EVIDENCE_SIGNAL_HIERARCHY.md`, `CRAVE_DESIGN_SYSTEM.md`, and the shipped `PlaceRanking` score-band contract.

Forward implementation: `frontend/src/utils/rankScore.ts`, Rank Home grouping, Profile-to-Rank ownership migration, and tests covering the tier boundary at 8.3 plus `disliked` exclusion.
