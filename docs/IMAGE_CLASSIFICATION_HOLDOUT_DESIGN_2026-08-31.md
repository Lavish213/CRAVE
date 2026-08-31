# Image classification holdout — experiment design (2026-08-31)

Addresses Master Plan item B1. This is a design document, not code — per
the plan's own instruction, this needs an actual experiment design before
anything gets built, not a rerun of the existing weak heuristic.

## The finding that changes the plan

The prior audit's step 3 said "run the already-bundled TFLite classifier"
without naming it. Checked the code: **`app/services/video/food_classifier.py`
is a real MobileNetV2 model (`food_classifier.tflite`, Food-101-derived
labels), currently applied only to video frames** (`score_video()`,
`find_best_highlight_window()`). Its actual per-frame scorer,
`_score_frame(interpreter, image_path) -> float`, takes any local image
file path — nothing about it is video-specific. This is a real ML
classifier, not the regex/URL-keyword heuristic in
`app/services/images/image_classifier.py` (`ImageClassifier`) that the
77,701-`unknown` finding is actually about.

**This means the classification gap isn't "we need to build a
classifier" — it's "the classifier that already exists and works has
never been pointed at place images."** That changes the shape of the
whole experiment: reuse `food_classifier.py`'s model, don't design a new
one.

One caveat worth carrying into the threshold-setting step: the model has
no explicit non-food class — its own docstring says the max softmax
probability across ~101 Food-101 categories is used as a food-confidence
*proxy*, not a direct food/not-food decision. A real photo of a plated
dish should still score confidently on some food category, but this
means "food confidence" here is indirect, and the holdout comparison
(step 4 below) needs to actually verify that assumption holds for place
photos, not just trust it by analogy from video frames.

## Protocol

### 1. Sample design
Stratify the sample across two axes that the prior audit already
measured:
- **Current Phase 3 bucket**: gallery-only / hidden / candidate-primary /
  unknown (the heuristic classifier's own output categories).
- **Host**: opaque Google-hosted (`places.googleapis.com/.../photos/...`)
  vs. first-party website images. This split matters because the
  heuristic's own logic falls back to position-based scoring specifically
  *because* Google URLs carry no filename/path hints — the byte-based
  classifier is meant to replace exactly that guess, so the holdout needs
  enough Google-hosted examples to prove it actually can.

**Sample size**: 385 images gives a ±5% margin at 95% confidence for a
binary accuracy estimate (standard proportion sample-size formula,
n = 1.96²·p·(1-p)/E² at the conservative p=0.5). Round up to ~400,
split roughly evenly across the 2×4 = 8 strata (~50 each) so no stratum
is too thin to say anything about.

### 2. Fetch
Download one normalized thumbnail per sampled URL, cached by URL hash so
a re-run doesn't re-fetch. Respect the same network/access policy already
flagged in the prior audit — no scraping around access controls, no
retry-hammering a host that 403s.

### 3. Score
Add a small public wrapper to `food_classifier.py` (mirroring the
existing `score_video()` public function) that loads the interpreter
once and scores a single local image path — the interpreter-loading and
`_preprocess()` logic already there needs no changes, just a
non-video-specific entry point. Run it against every fetched thumbnail.

### 4. Manual holdout comparison — needs a human or Codex, not this session
This session can write the sampling/fetching/scoring code, but **cannot
view the actual images to build ground-truth labels** — no image-viewing
capability against arbitrary fetched content here, and no production
access to the real URLs anyway. Someone with both needs to hand-label
the ~400-image sample as food / not-food (interior, exterior, menu text,
irrelevant) before the model's scores can be evaluated against anything.
This is the one step in the whole protocol that's a hard blocker for this
session specifically.

### 5. Threshold selection
Once labeled, pick the score threshold that meets an asymmetric bar:
**precision matters more than recall here.** Wrongly promoting a bad
image to primary/visible is worse than leaving a real food photo
classified `unknown` (which just keeps today's status quo for that row —
reversible, not user-facing-wrong). Target ≥90% precision on the "food"
label at whatever recall that implies; do not average precision and
recall equally.

### 6. Staged promotion, not a mass rewrite
Write classifications with model/version/confidence lineage (so a later
model swap doesn't silently re-interpret old scores), and promote in
small batches with the same rollback-by-batch discipline as the
population canary — this is exactly the shape PR #61/#64/#71 already
established, reuse it rather than inventing a new mutation pattern for
images specifically.

## What this session can and can't do

**Can do now, without production access:** write the sampling query
(stratified, from a local/test dataset shape), the thumbnail-fetch-and-
cache scaffolding, and the `food_classifier.py` public wrapper — all as
reviewable, tested code, same as the rest of this session's work.

**Cannot do:** fetch real production image URLs (network egress blocked
in this session), or hand-label the holdout (no image-viewing capability
against fetched content, and no access to the real rows anyway). Steps
2 and 4 need Codex (production access) or you.

## Next action

If this design holds up, the buildable pieces (wrapper function, sampling
query, fetch/cache scaffolding) can be built next as their own scoped PR,
with steps 2 and 4 explicitly left to whoever has production/image access
— not silently assumed to also happen in this session.
