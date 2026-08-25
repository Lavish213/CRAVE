# CRAVE — Algorithms, Scores & Rankings

Five distinct systems compute a number and call it a "score." They don't
share formulas and shouldn't be confused with each other. This is what
each one actually does, as of the code today (2026-08-25).

---

## 1. Global Place Score — `rank_score` (`place_score_v4.py`)

**What it is:** the one objective, algorithmic quality score every place
gets, computed offline and stored on `Place.rank_score` (0.0–1.0). Every
other ranking system in the app *starts* from this number.

**5 buckets, summed:**

| Bucket | Cap / weight | Driven by |
|---|---|---|
| Structural | capped at **0.28** | images (0.10), completeness (0.10), menu (0.14), app/ordering link (0.10), recency (0.06) — deliberately under-weighted so data-richness alone can't dominate |
| Authenticity | base + up to +0.08 boost | blog mentions (0.12), creator/social mentions (0.10), hitlist saves (0.12) — each **gated** by mention count (0.25x below 2, 0.5x at 2–3, full weight at 4+), then a cross-source multiplier (1.15x for 2 independent signal types, 1.35x for 3) |
| Authority | additive, 0.08 max | awards/press — validates on top, doesn't get redistributed |
| Momentum | 0 (reserved) | not wired yet — placeholder for future velocity/trending signal |
| Hidden-gem boost | +0.05 to +0.10 | only fires when structural < 0.25 AND authenticity > 0.15 AND not already award-tier AND low risk — the mechanism meant to surface a cash-only TikTok find over a well-catalogued chain |

Risk score (editorial flags, negative mentions) is subtracted last, capped
at −0.08 so nothing gets zeroed out entirely.

**Known limitation (confirmed, being worked around — see §2):** almost
any normally-populated place (name, coordinates, a few photos, a website
or menu) hits close to the 0.28 structural cap by default, while
authenticity/authority stay near zero for most places in a cold-start
catalog with little real save/mention data yet. Result: most places
cluster tightly around 0.28, which is why absolute-threshold tiering
broke (next section).

---

## 2. City Percentile & Tier Badges (`rank_percentile_query.py`, `scoring.ts`)

**What it is:** the "CRAVE Pick / Hidden Gem / Worth Knowing / Explore"
badge shown on every place card. **Not** the same number as `rank_score`
directly — it's `rank_score` re-expressed as **standing within the
place's own city**.

- `city_ranking_worker.py` runs hourly (scheduled job `ranking_update`),
  sorts every active place in a city by `rank_score` DESC, and stores a
  1-indexed `rank_position` per place in `CityPlaceRanking`.
- `rank_percentile_query.py` converts that into `rank_percentile` ∈
  [0, 1] (1.0 = best in the city) via one SQL window-function query,
  attached to places right before they're sent to the app.
- `getTier()` (`scoring.ts`) buckets on **percentile**, not raw score:

  | Percentile | Tier |
  |---|---|
  | ≥ 0.95 | CRAVE Pick |
  | ≥ 0.80 | Hidden Gem |
  | ≥ 0.40 | Worth Knowing |
  | below | Explore |

  Falls back to the old absolute-score bands (0.42/0.32/0.22) only for a
  place with no ranking snapshot yet (just added, before the next hourly
  run).

**Why percentile and not re-tuned absolute numbers:** the app is
pre-launch with almost no real save/mention data yet, so any absolute
threshold tuned against today's distribution would need retuning again
the moment real usage starts shifting it. Percentile is self-correcting —
"top 5% of this city" stays true regardless of how the underlying score
curve moves.

---

## 3. Feed Ranking (`feed_ranker.py`)

**What it is:** the actual sort order on the Feed screen. Takes
`rank_score` and blends in context the global score alone doesn't carry.

```
final_score = rank_score × 0.65
            + proximity  × 0.20   (0 if no location)
            + quality    × 0.10   (small tie-breaker bonus)
            + explore    × 0.05   (deterministic pseudo-variety)
            + saturation_penalty
            + chain_penalty
```

- **Proximity**: `1 / (1 + miles/10)` — 0mi→1.0, 5mi→0.67, 10mi→0.5,
  20mi→0.33.
- **Quality bonus** (max 0.025): small amplifiers for website/address/
  multiple specific categories — tie-breaking only, not a real signal on
  its own (those are already in `rank_score`).
- **Explore boost**: ~15% of places get a +0.01–0.03 bump, seeded
  deterministically off `CRC32(place_id)` — same place always gets the
  same boost, so results are stable per-place but don't feel purely
  score-sorted.
- **Saturation penalty**: −0.01 to −0.03 when a category has 5+/10+/20+
  candidates in the pool, applied *before* diversity so the diversity
  pass has less work to do.
- **Chain penalty**: flat −0.06 for ~50 known national chains (McDonald's,
  Starbucks, Chipotle, Trader Joe's, etc. — matched by substring in the
  name). CRAVE is positioned as local discovery; chains are already
  findable everywhere.
- **Diversity pass** (after scoring): greedy scan enforcing no 2
  consecutive same-category picks and max 3 of one category per 10-item
  window — reorders around the score ranking rather than replacing it.

City feeds are additionally cached as a pre-built "bucket" of place IDs
(`feed_bucket_manager.py`) to avoid recomputing this per-request.

---

## 4. Search Ordering (`search_query.py` / `search_engine.py`)

Not a scored blend — a straightforward SQL ordering:

- **With a location**: order by `(distance)² ASC, rank_score DESC, id ASC`
  — a real nearby name match is guaranteed into the result window by
  distance first, so it can't be crowded out by unrelated higher-scored
  places elsewhere. `rank_score` only breaks ties among similarly-distant
  results.
- **Without a location**: `rank_score DESC, id ASC` globally.
- Deliberately searches the **whole catalog**, not scoped to the
  currently-selected city — a fix for an earlier bug where a real match
  outside the selected city returned nothing.

Search results now also carry `rank_percentile` (§2) for tier badges,
same as Feed.

---

## 5. Personal Ranking Engine (`ranking_service.py`)

**What it is:** your own subjective per-place ranking (the "rank this
place" flow) — a completely separate number from `rank_score`, stored
per-user on `PlaceRanking.rank_score`. Reverse-engineered from how Beli's
comparison flow works, with two deliberate deviations.

**Mechanism:**
1. Pick a coarse tier for the place you just ranked.
2. The engine binary-searches your existing ranked list *within that
   tier, scoped to the same cuisine category* — "which was better, this
   or X?" — narrowing a `[lo, hi)` index range each round.
3. When the range converges, your final score is the midpoint between
   the two neighbors it landed between (or the tier's band midpoint if
   you're the first entry).

**Two deviations from Beli, both addressing its most common user
complaint:**
- Comparisons are **cuisine-scoped**, not global — you're never asked to
  judge a taco truck against a steakhouse. This makes `rank_score` a
  same-cuisine ordering mapped onto the tier band, not a strict
  cross-cuisine total order.
- **"Skip"** is a third valid answer ("I can't call this one") — it
  converges immediately at the current midpoint instead of forcing a
  verdict.

Session state between comparison rounds is a short-lived signed JWT (15
min TTL), not a DB row — nothing to clean up, tamper-proof via the app's
own `secret_key`.

---

## 6. Video Food Classifier (moderation gate, not a ranking)

Separate system entirely — MobileNetV2-based TFLite model
(`food_classifier.py`) scoring how confident the model is that an
uploaded video frame shows food (82 ingredient classes). Threshold 0.8
(real gap observed in testing: food scores 0.988–1.000, non-food
0.52–0.57). **Known blind spot**: no explicit "not food" class, so
content unlike anything in training data can still score confidently —
not fixable by threshold tuning alone.

---

## Quick reference: which number, where

| Screen/feature | What orders it |
|---|---|
| Feed | `feed_ranker.py` blended score |
| Search | distance + `rank_score`, plain SQL order |
| Tier badge (any screen) | `rank_percentile` (city-scoped), falls back to `rank_score` |
| "Rank this place" / your own list | `PlaceRanking.rank_score` (personal, comparison-based) |
| Leaderboard / friend rankings | aggregates `PlaceRanking` (personal engine), not `rank_score` |
| Video upload gate | food classifier confidence, unrelated to any place score |
