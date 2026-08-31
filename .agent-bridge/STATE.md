# Active agent state

Status: idle
Owner: Claude
Branch: main
Base SHA: c5ff3292b2f1cec05f7223cc3c0870deae79bb63
Scope: Worked through Master Plan items directly per the user's "chat down,
you go" instruction, since Codex's session is offline. Merged PR #74
(A2 throughput bounding + A6 dead code cleanup) and PR #75
(A4 BentoBox adapter).

Done this pass:
- A2: added MAX_API_PROBE_SECONDS (20s) / MAX_IFRAME_PROBE_SECONDS (15s)
  wall-clock budgets in menu_extraction_router.py. Confirmed the actual
  math behind the 17-minute run: up to 20 API-endpoint candidates x ~8s
  timeout each = up to ~160s on that one sub-stage alone, per place, with
  only a count cap before this fix, no time cap.
- A6: deleted menu_link_finder.py, menu_link_discovery.py,
  menu_site_crawler.py -- confirmed zero callers repo-wide.
- A4: added bentobox_extractor.py -- BentoBox has no JSON ordering API to
  build a normal adapter against, so this handles the one confirmed-real
  pattern (a static PDF menu on bentoboxcdn.com/getbento.com, evidenced by
  the North Beach Sandwicheez entity review) via the existing
  extract_pdf_menu(). Registered in provider_registry.py.

Partial / needs your production access:
- A3 (the 2 historical Square/Toast sources): traced as far as static code
  analysis allows. Ruled out one hypothesis -- provider_registry.py's
  MIN_VALID_ITEMS=2 gate and menu_claim_emitter.py's MIN_ITEMS_TO_EMIT=2
  are numerically aligned, so a sub-2-item extraction can't slip through
  the registry and then get killed at the claims stage; that's not the
  mismatch. Could not go further without the actual PlaceClaim/PlaceTruth
  rows for Itani Ramen (Toast) and Reem's California (Square) -- I have no
  production DB access in this session. Needs your query access to see
  what these two sources' claims actually contained (if any) between
  extraction and canonical publish.

Locked files: none currently held.
Verification plan: full backend suite green on each change (896, then 902
passed, 2 skipped); each new/changed test independently verified to catch
its corresponding regression (temporarily reverted, watched fail, restored).
Next action: Codex, when back: (1) review/merge PR #75 if not already done,
(2) finish A3 with actual production data using the ruled-out hypothesis
above as a starting point, (3) continue with Master Plan sequencing --
A1 (run the 13,148 backlog) is next now that A2/A6 are done, then A7/A5.

## Existing local work excluded from this bridge

`eas.json`, `package.json`, `frontend/package-lock.json`, `.agents/`, and
`docs/CRAVE_MASTER_EXECUTION_ROADMAP.md` were already dirty when this
bridge was created. They are not owned by this task.
