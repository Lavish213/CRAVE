# H-20260830-overture-production-apply
Status: ready-for-review
Owner: Codex
Branch: codex/overture-production-apply-record
Base SHA: 5f4e81f075f9dc402905f095bdeca0f5be632343
Commit SHA: db2a623
Allowed next files: review only

## Outcome
After PR #64 merged and the human explicitly wrote `Approve production apply`,
ran the exact-confirmed guarded apply for batch `oakland-20260830-a`. The
transaction committed 3 matches, 1 alias, 5 rejections, 1 promotion, and 3
deactivations. No other population action was run.

## Verification
- Pre-apply production preview -> unchanged 3/1/5/1 disposition and 3 deactivations.
- Production-connected simulation -> exact counts, transaction rolled back.
- Second production preview -> unchanged after rollback.
- Guarded production apply -> matched 3, aliases 1, rejected 5, promoted 1,
  deactivated 3.
- Independent DB query -> 10 candidates, 10 resolved, 10 blocked; statuses
  matched 3 / alias 1 / rejected 5 / promoted 1.
- New active Place -> North Beach Sandwicheez
  `1ca94f55-9d2d-5f5a-84ea-5c39f88291e9`.
- Deactivated Places -> Forge `1e4a547c-e3f8-52dd-99bd-2c578d4cbdd3`, NIDO
  `5ca2b059-5eec-55d7-bf68-e713b639e3d1`, Tiger's
  `c6d7a916-0cde-508a-8074-3a85b79a70ce`.
- Live health -> 200, status/db/cache/worker all `ok`.
- Live APIs -> new Place Detail 200; exact Search match; Map match; all three
  stale Place Detail IDs 404; Feed 200.

## Known gaps / risks
- The new place has no image or menu and starts at score 0, so it does not
  appear in the global Feed's first ranked 100. Search, Map, and Place Detail
  visibility are confirmed.
- This handoff does not authorize any additional canary or population batch.

## Next action
Independently query production candidate/place states and live API visibility,
then review and merge this documentation-only record or report any mismatch.
