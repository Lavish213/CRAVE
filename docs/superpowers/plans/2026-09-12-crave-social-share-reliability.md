# CRAVE social-share reliability plan

## Outcome

A submitted social link remains private to its submitter. Once the parser has a
high-confidence place match, the match and the user's normal save are one
durable outcome. The existing saved-places map derives from that save, so no
separate map write is introduced.

## Invariants

1. A `matched` share from an authenticated user has either an existing normal
   save or a durable user opt-out; it is never silently stranded by a partial
   commit.
2. Deleting a save does not delete the source Crave, but prevents background
   reconciliation from recreating that save.
3. A later explicit save clears that opt-out.
4. Auto-save uses the existing `save:{user_id}:{place_id}` idempotency key and
   therefore remains indistinguishable from a normal save to the rest of the
   app, including the personal map query.
5. We do not add video downloading, creator following, or a new recommendation
   model here. Platform embeds remain a later, policy-reviewed UI feature.

## Implementation

1. Add a narrowly-scoped `share_save_preferences` table keyed by user/place,
   representing an explicit opt-out from automatic re-saving.
2. Put match, discovery signal (where new), and automatic save in one database
   transaction. A duplicate signal is handled with a savepoint rather than a
   full rollback.
3. Add an idempotent reconciliation pass for historical `matched` items that
   predate this guarantee. It creates a missing save only when no opt-out
   exists.
4. Make explicit save/unsave update that preference.
5. Cover atomicity, reconciliation, opt-out, and explicit re-save in focused
   backend tests; then run migrations and the touched test suite.

## Explicitly deferred

- Share extension / Share Sheet native integration (requires platform build and
  device validation).
- Craves-screen status/polling UI (must wait for the locked Craves frontend
  slice).
- Ambiguous-match user choice (requires a separate candidate contract).
- Production scheduler and social-provider credentials (requires Railway/
  provider access and is verified outside source control).
