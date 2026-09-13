# Search / Map V1.5 Screen Mockups

Status date: September 7, 2026  
Status: Propagated screen mockups, not Penpot implementation-ready  
Input artifacts:

- `docs/design/SEARCH_MAP_V15_REAL_MOCKUPS.md`
- `docs/design/SEARCH_MAP_V15_RESILIENCE_PROOF.md`
- `docs/design/SEARCH_MAP_V15_COMPONENT_ANATOMY.md`

## Purpose

This package turns the approved Search/Map V1.5 visual grammar into actual app-screen mockups across the 16 required states.

The rule for this pass: compose approved components only. Do not invent a new badge, color meaning, recovery pattern, or map ownership model inside a single state.

## Frozen Screen Grammar

1. Search answer grammar: `intent -> interpretation -> answer -> reason -> alternatives`.
2. Result hierarchy: `1 dominant answer -> supporting answers -> bounded remainder`.
3. Recovery grammar: `wanted -> protected -> conflict -> smallest truthful action`.
4. Search/Map ownership: `Search owns candidates -> Map spatializes candidates -> Search This Area creates a new set`.
5. Evidence honesty: missing, stale, weak, or uncertain data must be visible without turning the restaurant into an error.

## Mocked States

1. Search Home
2. Near Me Populated
3. City Populated
4. Map Context
5. Search This Area
6. Zero Results
7. Relaxed Results
8. Hard Constraint No Relaxation
9. Missing Image
10. Low Confidence
11. Location Denied
12. Location Unavailable
13. Loading
14. Error / Retry
15. Large Text
16. Screen Reader

## Brutal Grade

8.8/10.

This is a real propagation board now, not just a strategy poster. The system holds together across all 16 states, the state language is consistent, and Search/Map ownership stays intact.

What keeps it below 9.5:

- The SVG still uses drawn placeholder media, not real photo assets.
- Accessibility is visually represented, not simulator/device proven.
- Component dimensions are directional, not implementation tokens.
- Some copy will need tightening against real backend payloads.

## Promotion Recommendation

Promote this artifact to: `16-state visual propagation draft`.

Do not promote to:

- Penpot implementation-ready.
- Device verified.
- Final Wave 5.

## Next Gate

Run an accessibility-size and real-photo pass on these exact 16 states. If no new component language is required, then translate into Penpot.
