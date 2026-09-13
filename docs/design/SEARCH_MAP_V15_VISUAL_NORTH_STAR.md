# Search / Map V1.5 Visual North Star

Status date: September 7, 2026  
Status: Audited visual north star  
Source: Human-supplied refined five-screen visual board in Codex conversation  
Grade: 9.3/10 direction

## Decision

Freeze the supplied five-screen visual direction as the Search/Map V1.5 visual north star.

This is not a new product direction. It is the corrected presentation layer for the already-approved Search/Map V1.5 contract.

## Status Boundaries

This artifact is:

- Audited visual direction.
- The source of truth for Search/Map visual grammar.
- Ready to propagate across the full Search/Map state inventory.

This artifact is not:

- Final.
- Locked for implementation.
- Penpot implementation-ready.
- Device verified.
- Proof that production data/photos behave correctly.

## What Is Now Preserved

### Visual grammar

- Dark cinematic shell.
- Food-led hierarchy.
- Warm orange/gold accent.
- Reduced container dependency.
- Fewer beige surfaces.
- Editorial reason copy attached to the recommendation.
- Large, appetite-forward hero photography.
- Calm, premium board rhythm.

### Product grammar

- Search owns candidates.
- Map spatializes candidates.
- Map does not independently recommend.
- The candidate set only changes after an explicit Search This Area action.
- Hard constraints cannot be silently relaxed.
- Relaxation must be explicit, specific, and reversible.
- Low confidence means CRAVE is still learning; it does not mean the restaurant is bad.
- Missing media becomes a deliberate identity treatment, not a broken-photo state.

## Required Refinements Before Propagation

These are refinements, not a reason to restart exploration.

1. Recovery truth: for the shown zero-result query, `Outdoor seating` must be `Required` if it is the blocker. If it is only preferred, the screen must not say no matches right now.
2. Search Results: remove or hide `Dishes` and `Lists` until those surfaces are genuinely supported.
3. Map: keep the selected pin dominant and reduce unselected-pin contrast.
4. Copy: standardize around `Food finds you.` and `Real food. Real places. Right now.`
5. Low confidence: preserve calm `Still learning` language.
6. No-photo: preserve branded identity treatment.
7. Photography: validate with real CRAVE data and device screenshots before any implementation-ready claim.

## Propagation Rule

Propagate this exact visual grammar across the full Search/Map state inventory.

Do not redesign the system during propagation.

If a state cannot be expressed with this grammar, stop and flag the collision. Return the issue to the component contract instead of improvising a one-off visual solution.

## Path From 9.3 To 9.5+

- Fix the recovery required/preferred contradiction.
- Remove unsupported Search tabs.
- Quiet unselected Map pins.
- Run real-photo stress testing.
- Run large-text and VoiceOver verification.
- Propagate across the 16 Search/Map states without visual drift.

## Next Step

Build `Search / Map V1.5 — North Star Propagation`:

- Use this visual direction.
- Cover all approved Search/Map states.
- Annotate only truth-critical differences.
- Keep status at `Propagation draft` until accessibility, real-photo, Penpot, and device checks pass.
