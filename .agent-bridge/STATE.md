# Active agent state

Status: ready-for-review
Owner: Codex
Branch: codex/map-truth-and-clustering
Base SHA: f8a7f751d9837314ab02eeed326348db7d32249e
Scope: Fix verified Map truth/error semantics and replace the marker-cloud
grid with screen-space progressive clustering; no visual redesign or
production writes.
Locked files: `backend/app/services/query/map_query.py`,
`backend/app/api/v1/routes/map.py`, `backend/tests/map/`,
`backend/tests/test_map_query.py`, `frontend/app/(tabs)/map.tsx`,
`frontend/src/components/MapMarker.tsx`, `frontend/__tests__/map.test.tsx`,
`.agent-bridge/STATE.md`, `.agent-bridge/codex-to-claude.md`
Verification plan: Run focused backend/frontend Map tests, full
backend/frontend suites, typecheck, and fresh simulator screenshots if the
current native environment can load the API.
Next action: Claude independently inspects commit `e26e67a`, reruns the Map
checks, reviews `/private/tmp/crave-map-after-collision-clustering.png`, and
merges only if the diff and native behavior agree with the evidence.

## Existing local work excluded from this bridge

`eas.json`, `package.json`, `frontend/package-lock.json`, `.agents/`, and
`docs/CRAVE_MASTER_EXECUTION_ROADMAP.md` were already dirty when this
bridge was created. They are not owned by this task.
