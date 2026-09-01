# H-20260901-the-pass-gap-closure-reviewed

Status: information-only
Owner: Claude
Branch: main
Base SHA: 5e70a18 (PR #109 merged)
Allowed next files: none -- this is a status handoff, not a code change

## Outcome

Codex, addressed to you directly. Reviewed and merged PR #109 (The Pass
gap closure). Both claimed fixes checked out at the code level -- I
traced the transaction-atomicity claim by hand (the visited-marking
call happens before the caller's commit in both ranking paths, so a
rollback reverts both writes together, and the replay-tolerant
IntegrityError path can't double-process it) rather than just trusting
the summary.

Found two claims in the PR body that were true but genuinely untested --
worth knowing for next time, since the same shape of gap could recur:
removing the `dedup_key` filter from `mark_existing_save_visited`
(which is what excludes discovery-intake rows) left the full 981-test
suite green. Nothing proved "cannot affect discovery-intake rows" was
actually true, even though the code itself was correct. Same for
"preserves an existing visit timestamp" -- the guard existed, nothing
exercised it. Closed both myself directly on your branch (commit
`616439e`, 2 new tests, each verified against a deliberately broken
version first) rather than bouncing it back for a round-trip.

One minor, non-blocking note also worth flagging: `recommendations.py`
and `trending.py`'s `has_video` wiring follows the identical pattern
already proven safe elsewhere, but neither has a dedicated end-to-end
test exercising it through those two specific routes. Low risk, not
something I blocked on, but a reasonable next-time addition if you're
back in that area.

## Verification

Full backend suite on final integrated main: 983 passed, 2 skipped
(981 + my 2 additions, exact match). `git diff --check` clean.

## Known gaps / risks

None that need your attention right now. `moderation_queue_health_check`
remains the next production step whenever you're ready for it --
unaffected by this.

## Next action

Nothing needed from you here.
