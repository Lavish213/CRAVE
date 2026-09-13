# Search / Map V1.5 — Pre-Penpot Proof Package

**Status:** Pre-Penpot proof package — NOT YET APPROVED  
**Governing status:** Visual North Star / Propagation Draft with unresolved proof gaps

## Canonical inventory
SM-01 Search Home; SM-02 Input Active; SM-03 Results; SM-04 Map; SM-05 Required Constraint Zero Result; SM-06 Preferred Constraint No Exact Match; SM-07 Personalization Low Confidence; SM-08 Missing Media; SM-09 Closed Place; SM-10 Location Permission Denied; SM-11 Location Unavailable; SM-12 Long Restaurant Name; SM-13 Stale Hours; SM-14 Filter Editing; SM-15 Save Confirmation; SM-16 Native Share Transition.

Place Detail is an adjacent continuation and is not counted as a Search/Map state.

## Core journey
`SM-01 → SM-02 → SM-03 → SM-04 → Adjacent Place Detail/action`

SM-03 must show query/context, result count and preserved constraints, one food-forward top candidate, at least two scannable alternatives, refinement access, and bounded Show More. SM-04 spatializes the Search-owned candidate set and never independently reranks it.

## Supporting / edge-state contract
Every state is documented as: **Trigger → truth communicated → primary action → secondary action → transition → forbidden behavior.**

- **SM-05:** hard constraint blocks all candidates. Never silently relax it. Continue only with options that still satisfy every hard constraint; otherwise name the exact proposed change and require user action.
- **SM-06:** a preference failed but valid candidates remain. Show valid nearby options; do not claim there are no results.
- **SM-07:** plausible fit with weak personal evidence. `Still learning` is allowed only for this kind of personalization uncertainty. Never frame it as restaurant danger/quality.
- **SM-08:** missing media uses deliberate identity treatment, never broken-photo styling.
- **SM-09:** closed status is operational information, separate from recommendation quality.
- **SM-10:** permission denied offers Settings and city/area Search; no re-request loop.
- **SM-11:** location unavailable offers retry, trustworthy last-known area, or city/area Search; do not confuse with denied permission.
- **SM-14:** filter edits preserve query/interpretation; hard constraints change only explicitly.
- **SM-15:** Save → toast/inline confirmation → remain in context; optional View in Craves.
- **SM-16:** CRAVE owns the Share action/payload; the OS owns the share sheet.

## Uncertainty language
Use concrete uncertainty when known: `Hours not recently verified`, `Limited menu information`, `Photo unavailable`, `Few matching saves yet`. Reserve `Still learning` for genuine personalization-confidence uncertainty. Missing evidence is not negative evidence.

## Recovery hierarchy
When a valid forward path exists: **See nearby options** is primary and **Edit search** secondary. If continuing requires changing a hard constraint, state the exact change and require explicit confirmation.

## Color semantics
Warm gold/orange is narrowed to brand, selection, and primary action. Separate semantic treatments are required for positive operational state, uncertainty/stale data, protected hard constraints, destructive actions, and neutral metadata. Meaning must never rely on color alone. Mockup colors are not production tokens until contrast is measured.

## Resilience proof
Photography torture suite: excellent, average UGC, dark, overexposed, exterior, signage, wrong subject/focal point, portrait crop, extreme landscape crop, blurry, missing, failed load.

Content torture suite: short and 60+ character names, long location, 1-line and 3-line reasons, missing price, stale hours, missing menu, partial metadata, multiple dietary constraints, and localization expansion. Never solve failures by shrinking below accessibility requirements.

## Accessibility evidence gate
Mockup labels are not proof. Before approval, capture:
- measured foreground/background contrast;
- default, large, accessibility-large, and maximum-supported Dynamic Type renders;
- complete screen-reader/focus order for critical screens;
- measured interactive targets, using a 44×44 pt iOS-oriented baseline unless a documented exception applies;
- Reduced Motion behavior;
- non-color Map selection;
- list-equivalent access for meaningful Map workflows.

## Pre-Penpot audit
- [ ] SM-01–SM-16 uniquely represented
- [ ] Place Detail marked adjacent
- [ ] no fake sequential edge states
- [ ] Results proves comparison with 3+ visible candidates
- [ ] no silent hard-constraint relaxation
- [ ] valid forward recovery prioritized
- [ ] concrete uncertainty used when known
- [ ] Save remains in context
- [ ] Share remains OS-owned after invocation
- [ ] semantic color roles separated
- [ ] hostile photography reviewed
- [ ] hostile content reviewed
- [ ] contrast measured
- [ ] Dynamic Type rendered
- [ ] screen-reader order documented/verified
- [ ] touch targets measured
- [ ] Reduced Motion defined
- [ ] Map selection works without color
- [ ] Map/list equivalence preserved
- [ ] no hidden product/UX/data ambiguity

## Current approval decision
**NOT YET APPROVED.** The corrected state matrix and frozen visual grammar are sufficient to proceed through proof work, but hostile-data evidence and measured accessibility evidence are still required. Approval is a deliberate gate, not a visual-quality judgment.

## Penpot entry gate
Only after the audit passes and status is explicitly promoted to **Approved**. Penpot then receives tokens/semantic roles, typography, spacing/radius, component families/variants, SM-01–SM-16, Core Journey, edge annotations, resilience cases, accessibility annotations, motion guidance, microcopy, and component-to-screen mapping.

Penpot build order after approval:
1. Foundations
2. Primitives
3. CRAVE product components
4. SM-01–SM-04 core screens
5. SM-05–SM-11 and SM-14–SM-16 variants
6. SM-12/SM-13 and hostile-data variants
7. accessibility annotations/prototype transitions
8. final matrix audit

## Promotion ladder
`Visual North Star → Corrected State Matrix → Core Journey → Supporting/Edge Proof → Resilience/Accessibility Proof → Audit → Corrections → Approved → Penpot → Implementation-ready → Codex → Device Verification → Final`
