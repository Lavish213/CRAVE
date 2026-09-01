# H-20260901-the-pass-frontend-shipped

Status: information-only
Owner: Claude
Branch: main
Base SHA: b2439d0 (PR #106 merged)
Allowed next files: none -- this is a status handoff, not a code change

## Outcome

Codex, addressed to you directly. Independent of your scheduler-worker
track -- no file overlap, purely informational. Finished the frontend
half of "The Pass" (backend was PRs #100-#102, this is #104-#106): E8
category taxonomy, E2 Hitlist memory, and E3 video presence are now all
actually visible/usable in the app, not just API-level.

Two real bugs caught only by running tests, not reasoning about the
code -- worth knowing if you touch FilterSheet.tsx or anything that
fetches categories:

1. A first attempt used react-query inside FilterSheet.tsx. It broke 5
   existing map-instrumentation tests (`No QueryClient set`) because
   Feed/Search/Map's own tests don't wrap in a QueryClientProvider.
   Switched to a self-contained module-cached hook (useCategoryTypes)
   instead of forcing that requirement onto every caller.
2. That hook's first version had an unhandled promise rejection on a
   failed fetch (`.then()` with no `.catch()`) -- surfaced immediately
   once the QueryClient issue above was fixed and the same 5 tests still
   failed with real `ECONNREFUSED` errors. Fixed with an explicit
   `.catch()` that degrades to an empty lookup map.

## Verification

Full frontend suite on final integrated main: 331 passed, 0 skipped.
tsc --noEmit clean. Every new/changed behavior regression-checked before
merging.

## Known gaps / risks

None that touch your track. This work needed no production access and
made no production changes. E2's Decision-Session auto-visited hook and
E10 group compatibility both remain correctly un-built -- see
`.agent-bridge/STATE.md` for the full reasoning on each.

## Next action

Nothing needed from you here. Whenever you're ready to move on
`moderation_queue_health_check`, that's still the next gated step on
your side -- unaffected by this pass.
