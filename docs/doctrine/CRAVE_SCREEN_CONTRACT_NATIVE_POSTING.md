# CRAVE Screen Contract — Native Posting / Private Logging Composer

**Status:** Draft contract, pending audit/freeze (2026-09-07)
**Reconciliation basis:** No current equivalent exists. `record-video/
[placeId].tsx` (camera capture, permission handling, shot templates,
recording prompts) and `add-spot.tsx` (restaurant search/candidate
submission) are partial precursors, not equivalents — this contract
defines the composer that reuses their real, working code rather than
rebuilding it, per the Target Screen Registry's already-resolved MERGE
finding.

---

## 1. Purpose

The "record food evidence" surface (`CRAVE_ROUTE_FLOW_MAP.md` §2) — the
persistent `+` action's destination. **One shared entry architecture,
two distinct outcomes:** a private log (personal record only) and a
native post (structured, shared evidence). These are not one action
with a visibility toggle bolted on — they diverge in requirements, not
just in who can see the result (§9 makes this explicit).

## 2. User objective

Record what was eaten, honestly and fast — for personal memory alone,
or to share — without being blocked by imperfect restaurant/dish
identification.

## 3. Entry points

- **Persistent `+`** (tab-bar-adjacent action, any tab) — full flow,
  starting at the capture sheet (§6, Step 1).
- **Place Detail's "I ate here"** (that contract's §11) — a **fast
  path into this same composer**, restaurant pre-confirmed, skipping
  Steps 1-2 entirely, landing directly on Step 4. This is a
  reconciliation this contract makes explicit: "I ate here" was never
  meant to be a second, separate logging mechanism — it's this
  composer entered with one step already satisfied.

## 4. Exit points

Publish (private log or post, §9), or abandoning mid-composer — a
valid outcome, never forced to completion, consistent with the
confident-no principle generalized to this flow.

---

## 5. First viewport

Capture sheet (Take Photo / Choose Photo / Choose Video) on a full
`+` entry; the quick-take/visibility steps directly on Place Detail's
fast-path entry (§3).

---

## 6. Steps — conditional, not all always shown

1. **Capture** (skipped on the Place Detail fast path) — Take Photo /
   Choose Photo / Choose Video.
2. **Restaurant identification** (skipped on the Place Detail fast
   path, where it's already known) — confidence-gated: high confidence
   shows "Looks like you're at X — Confirm"; low/no confidence falls to
   manual search, reusing `add-spot.tsx`'s existing search UI verbatim,
   never a blocked flow.
3. **Dish identification** (optional, evidence-gated on real menu data
   existing for the confirmed restaurant) — "Is this the [dish]?" with
   an easy correction or "something else" fallback.
4. **Quick-Take Reaction** (optional, but the composer's main
   preference-bearing moment) — Loved it / Good / Not for me.
5. **Caption** (optional, always) — free text, never treated as
   structured evidence (§11).
6. **Visibility choice** (the one true requirement beyond a confirmed
   restaurant) — private / friends / public, remembered default always
   shown and overridable. **Public/friends are only enabled once media
   exists** (§9); reaching this step without media (the Place Detail
   fast path) shows private as available and an inline "add a photo or
   video to share this" affordance that opens Step 1 retroactively if
   the user wants to upgrade to a post.

---

## 7. Component tree

```
PostingComposer
├─ CaptureSheet (conditional)
│   ├─ VideoTemplateStrip   (existing, relocated verbatim -- Component Registry §2 F)
│   └─ BeatCueOverlay        (existing, relocated verbatim)
├─ RestaurantIdentification (conditional)
│   ├─ ConfidenceSuggestion
│   └─ ManualSearchFallback  (reuses add-spot.tsx's search UI)
├─ DishIdentification (conditional, evidence-gated)
├─ QuickTakeReaction         (new -- Component Registry §3.4)
├─ CaptionInput
└─ VisibilityChoice
```

## 8. Component reuse / new components

**Reused, relocated verbatim (not rewritten):** `VideoTemplateStrip`,
`BeatCueOverlay` (camera capture/permission-handling code and shot-
template mechanics from `record-video`), `add-spot.tsx`'s search flow
(identification fallback).

**Extended:** `PlaceVideoGallery`'s "record a new one" entry point now
opens this composer instead of `record-video` directly (Component
Registry §2 F) — its read-only gallery display is unaffected.

**New:** the Quick-Take Reaction control (Component Registry §3.4).

---

## 9. Private log vs. native post — the two outcomes, explicitly separated

| | Private log | Native post |
|---|---|---|
| Media required? | **No** (V1 Scope §5.1) | **Yes**, photo-led, single media, no carousel |
| Visibility | Private, always | Friends or public, explicit choice |
| Restaurant/dish ID confirmation | Same requirement either way — both always confirmed before completing, never skipped for either outcome | Same |
| Caption | Optional, never structured evidence | Same |
| Reaction → evidence | Structured meal reaction evidence (Evidence Hierarchy §3.7), identical weight regardless of visibility — **visibility never changes recommendation weight** (Evidence Hierarchy §3.11) | Same |
| Correction/deletion | Edit/delete anytime; retracts derived evidence (Data & State Map §5) | Same, plus retracts `source_type: organic_user` social evidence (§7) |
| Who can see it | Only the user | Chosen audience (friends/public) |
| Comments | N/A | **None, ever** — durable prohibition (V1 Scope §5.2) |
| Reactions from others | N/A | Private "Made me crave this" only — reactor identity never shown to poster, no public count (Privacy Matrix E6) |

The divergence is in **requirements** (media), not merely rendering —
this is why the two are documented as distinct outcomes of one
composer, not one action with a visibility flag.

---

## 10. Restaurant/dish identification integrity

Confidence-gated at every step (§6.2/6.3); low confidence never blocks
the flow — manual correction is always one tap away. A wrong auto-
attached restaurant or dish pollutes the evidence graph, so neither is
allowed to be silently assumed; both require an explicit confirm tap
even at high confidence.

---

## 11. Evidence emitted

Publishing (either outcome) writes: a visit evidence record (`declared`
tier — this composer is one of Route & Flow Map F5.1's declared-tier
sources), a structured meal reaction if given (Evidence Hierarchy
§3.7), dish evidence if a dish was confirmed (§3.16, scope modifier
only), and — for a native post — social evidence with
`source_type: organic_user` (Data & State Map §7). **Captions never
become structured evidence** regardless of outcome (Evidence Hierarchy
§3.15) — this is identical for both private logs and posts. Evidence is
emitted only at publish, not at each intermediate step, so an abandoned
draft leaves no partial evidence behind.

---

## 12. State coverage table

| State | Behavior |
|---|---|
| Anonymous | Capture and drafting work; publish gates through F10 with the draft preserved and replayed post-auth. |
| Authenticated | Full flow. |
| Loading | N/A at the composer level — each step's own async action (identification lookup, upload) has its own inline progress state, not a whole-screen loader. |
| Success | Publish confirmation, returns to the entry point (Feed/Place Detail/wherever `+` was tapped). |
| Empty | N/A — every step either has content or is conditionally absent (§6). |
| Partial data | N/A — nothing here is fetched remote content with optional fields; every field is user-authored. |
| Stale | N/A — no cached remote data displayed in this flow. |
| Offline | Capture works fully offline; publish queues locally and syncs on reconnect — a private log with no media can complete entirely offline. |
| Permission-denied (camera) | Falls to photo-library selection (§13 fallback matrix). |
| Permission-denied (photo library, camera also denied) | Falls to a private, text-only log with no media at all — never a dead end. |
| Permission-denied (microphone) | Video capture proceeds without audio, or falls to photo capture. |
| Low-confidence (identification) | Manual search fallback (§6.2), never blocked. |
| Error (publish failure) | Draft is kept, retry available — never silently discarded. |
| Screen-specific: visibility upgrade without media | Public/friends disabled with an inline prompt to add media (§6.6). |

---

## 13. Cross-cutting fields

**Interactions:** per §6's step sequence; each step has a clear
next/skip affordance where optional.

**Navigation/transitions:** modal/full-screen composer flow, not a tab;
returns to its entry point on publish or dismissal.

**Data reads:** menu data for dish-identification suggestions (place
operational-data/dish contract, Data & State Map §6/§8), `add-spot`'s
existing search for the manual fallback.

**Data writes/evidence emitted:** per §11.

**Auth:** draft-stage none required; publish requires it (§12).

**Permissions:** camera, photo library, microphone (video audio only) —
all with named fallbacks (§12, §14).

**Accessibility:** auto-generated alt text for images where feasible,
editable by the poster at capture time (folds into the existing
confirmation steps rather than a separate accessibility-authoring
step); named typography roles; 44pt touch targets.

**Analytics:** `post_published`/`log_created` with visibility level
(Data & State Map, Route & Flow Map F6.4); this event is also the
visit-confirmation signal feeding Rank Home's queue (F5.1).

**Responsive behavior:** mobile portrait; camera/video capture is
inherently a native-only capability, no web equivalent is specified.

---

## 14. Permission failure matrix (this screen's specific instance of the Privacy Matrix's general one)

| Denied | Fallback |
|---|---|
| Camera | Photo-library selection. |
| Photo library (camera also denied) | Private, text-only log, no media. |
| Microphone | Silent video, or photo capture. |
| Both camera and library permanently blocked | Text-only private log remains fully available — logging is never entirely permission-gated. |

---

## 15. Prohibited behavior

- No forcing media for a private log.
- No silently defaulting visibility — always shown, always overridable.
- No treating captions as structured taste evidence.
- No public reaction counts or reactor-identity exposure, ever.
- No comments, ever (durable, not a launch simplification).
- No reposts or quote-posts.
- No blocking publish on low-confidence identification — manual
  correction is always available.
- No rebuilding `record-video`'s capture/permission code instead of
  relocating it.

---

## 16. Unresolved dependencies

- **Dish Intelligence data model** (Data & State Map §8) — the hard
  prerequisite for Step 3's evidence-gating; without it, dish
  identification cannot honestly claim to be evidence-backed.
- **API/Integration Contract** — literal upload/publish endpoint shape,
  idempotency for retried publishes, deferred to that artifact.

---

## 17. Codex implementation boundary

Codex may: build the composer's step flow; relocate `VideoTemplateStrip`/
`BeatCueOverlay`/`add-spot`'s search verbatim; build the Quick-Take
Reaction control; wire Place Detail's "I ate here" to this composer's
fast path.

Codex may **not**: require media for a private log; allow public/
friends visibility without media present; treat a caption as taste
evidence; add comments, reposts, or public reaction counts under any
framing; build dish identification without the Dish Intelligence model
backing it.

---

## 18. Acceptance criteria

- A private log completes fully with zero media, offline.
- A native post cannot reach "public"/"friends" without media attached.
- Place Detail's "I ate here" demonstrably lands on this same composer
  at Step 4, not a separate declare-only mechanism.
- `record-video`'s capture code is reused, not duplicated, verifiable
  by the actual component imports.
- Full frontend test suite + `tsc --noEmit` clean.

---

## 19. Traceability

**Backward:** `CRAVE_MASTER_PRODUCT_INTELLIGENCE_BIBLE.md` §20 (Social
Link Import — distinct pipeline, cross-referenced not reused here),
`CRAVE_V1_SCOPE.md` §5.1/§5.2, `CRAVE_TARGET_SCREEN_REGISTRY.md`
§5.4/§5.5/§5.6, `CRAVE_ROUTE_FLOW_MAP.md` F6, `CRAVE_DATA_STATE_MAP.md`
§4/§5/§7/§8, `CRAVE_PRIVACY_PERMISSION_MATRIX.md` E1-E6/Permission
Failure Matrix, `CRAVE_EVIDENCE_SIGNAL_HIERARCHY.md` §3.7/§3.11/§3.15/
§3.16, `CRAVE_COMPONENT_REGISTRY.md` §2 F/§3.4,
`CRAVE_SCREEN_CONTRACT_PLACE_DETAIL.md` (§11's "I ate here" hand-off),
`CRAVE_SCREEN_CONTRACT_RANK_HOME.md` (this composer's publish is a
`declared`-tier F5.1 source feeding that screen's queue).

**Forward:** the Activity Inbox contract (private reaction notices
surface there), the Requirements/Traceability Matrix, the future API/
Integration Contract (upload/publish endpoint shape).

---

## 20. Proposed status

**YELLOW — pending audit.** One real, named blocker: the Dish
Intelligence data model gates Step 3 specifically, not the whole
composer — a private/public log with no dish identification is fully
specifiable and buildable today.
