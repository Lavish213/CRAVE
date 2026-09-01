# Active agent state

Status: idle
Owner: Claude
Branch: main
Base SHA: de6f825 (PR #102 merged)
Scope: Built out "The Pass" -- the design plan resolving all four E8/E2/
E3/E10 open product decisions -- after the user asked me to finish work
an interrupted session had scoped but never pushed anywhere (verified:
no branch, no PR, no uncommitted local files existed anywhere in this
checkout for that work; nothing was recoverable, so this was built fresh
from the same architecture that session had reasoned through and relayed,
re-verified against the real code rather than trusted). Shipped as 3
independently reviewable PRs, each with its own tests and regression
checks, same discipline as every change this session.

## PR #100 -- category taxonomy (E8)

`CategoryType` extended cuisine/venue/specialty -> cuisine/venue/dietary/
ownership/occasion/recognition; `specialty` retired at the DB level (a
raw-string insert of "specialty" now fails the check constraint, not
just unused by convention). Migration retypes the 11 former-specialty
rows. `CategoryOut` now surfaces `type`. Filter-UI grouping (how to
*present* the six types) intentionally not included -- still needs a
product call per the design doc's own "Needs a human call" section.

Caught by this PR's own real-Postgres CI job (not local testing --
SQLite doesn't enforce VARCHAR length, Postgres does): `categories.type`
was VARCHAR(9), sized for "specialty"; "recognition" is 11 chars and the
data UPDATE failed outright on the first real-Postgres run. Fixed by
widening the column before the retype, verified both directions.

## PR #101 -- Hitlist memory (E2)

`HitlistSave` (the table `/saves` is actually backed by, confirmed
before writing anything) gets `visited`/`visited_at`/`notes`. New
`PATCH /saves/{place_id}/memory`, real PATCH semantics (omitted vs.
explicit `null` distinguished via `exclude_unset`), `visited_at`
server-derived and cleared on unmark rather than left stale. Scope note:
this is schema+API only -- the Decision-Session ranking hook that
auto-sets `visited=true` is separate follow-up work, not built here.

## PR #102 -- video presence badge (E3)

New `get_has_video_bulk()` (mirrors the existing primary-image bulk-load
shape), wired into every list-shaped card consumer: cursor feed, legacy
`/places`, `/search`, both Map query functions. Place Detail stays the
only playback surface -- badge only, not a new content surface, per the
doctrine-risk reasoning in the design doc (a Feed action or dedicated
tab is the highest-risk option, closest to TikTok's lane).

Needed a real fix beyond the query itself: `PlaceOut`/`PlaceCardOut`'s
`_inject_category` validators rebuild an explicit dict from the ORM
object rather than passing it through, so `has_video` was silently
dropped even when set as a real attribute until named in both
dict-building blocks -- caught by a dedicated regression test, not
inspection.

## Verification

Full backend suite on final integrated main: 976 passed, 2 skipped
(939 baseline + 21 category + 7 saves + 9 video, exact match). Every
new/changed migration tested both directions against a fresh SQLite
replay of the full chain. Every new/changed behavior independently
regression-checked (reverted, confirmed the test fails, restored) before
merging, including the real-Postgres column-width bug above.

## Known gaps / risks

None from this pass that need your attention -- all three PRs are merged
and green. The genuinely open items (Filter UI grouping, the
Decision-Session visited hook, and the E10 group-compatibility hold
condition) are documented above and in the design docs, not silently
dropped.

## Next action

Nothing needed from you on this pass. Standing by for the next
`moderation_queue_health_check` authorization request or whatever's next
on the production side -- unrelated track, no overlap with this work.

## Existing local work excluded from this bridge

The primary checkout's `eas.json`, `package.json`,
`frontend/package-lock.json`, `.agents/`, and
`docs/CRAVE_MASTER_EXECUTION_ROADMAP.md` remain unrelated and untouched.
