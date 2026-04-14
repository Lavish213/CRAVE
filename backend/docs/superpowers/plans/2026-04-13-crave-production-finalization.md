# CRAVE Production Finalization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix flat scoring, add Mapbox GeoJSON endpoint, build social intelligence layer, and ship Crave's Hit List — all additive, zero regressions.

**Architecture:** Option A — surgical targeted fixes only. Every change is a new file or a targeted edit to one function. No existing system is replaced or broken. Execution order: scoring → map geojson → social layer → hit list.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy 2.x, SQLite (dev) / Postgres (prod), Alembic, Pydantic v2, pytest

---

## File Map

### Phase 1 — Scoring

| Action | Path | Responsibility |
|---|---|---|
| CREATE | `app/services/scoring/signal_context.py` | Dataclass holding pre-fetched batch signal data |
| CREATE | `app/services/scoring/city_weight_profiles.py` | All city weight profiles, validated at import |
| CREATE | `app/services/scoring/place_score_v3.py` | Pure scoring function — no DB, fully testable |
| MODIFY | `app/workers/recompute_scores_worker.py` | Add batch signal fetch before scoring loop |
| CREATE | `tests/scoring/test_place_score_v3.py` | Tests for scoring logic |
| CREATE | `tests/scoring/test_city_weight_profiles.py` | Tests for profile validation + lookup |

### Phase 2 — Map GeoJSON

| Action | Path | Responsibility |
|---|---|---|
| MODIFY | `app/api/v1/schemas/map.py` | Add GeoJSON schema types |
| MODIFY | `app/services/query/map_query.py` | Add `fetch_places_for_map_geojson()` + tier helpers |
| MODIFY | `app/api/v1/routes/map.py` | Add `GET /map/geojson` route |
| CREATE | `tests/map/test_map_geojson.py` | Tests for tier logic and GeoJSON shape |

### Phase 3 — Social Intelligence Layer

| Action | Path | Responsibility |
|---|---|---|
| CREATE | `app/services/social/__init__.py` | Package init |
| CREATE | `app/services/social/platform_detect.py` | URL → platform slug |
| CREATE | `app/services/social/url_normalize.py` | Strip tracking params, normalize casing |
| CREATE | `app/services/social/caption_parser.py` | Extract hashtags, location lines, place candidates |
| CREATE | `app/services/social/extractors/__init__.py` | Package init |
| CREATE | `app/services/social/extractors/tiktok.py` | Pull creator handle from TikTok URL |
| CREATE | `app/services/social/extractors/instagram.py` | Pull handle from Instagram URL |
| CREATE | `app/services/social/extractors/youtube.py` | Pull channel handle from YouTube URL |
| CREATE | `tests/social/test_platform_detect.py` | Tests for platform detection |
| CREATE | `tests/social/test_url_normalize.py` | Tests for URL normalization |
| CREATE | `tests/social/test_caption_parser.py` | Tests for caption parsing |
| CREATE | `tests/social/test_extractors.py` | Tests for all three extractors |

### Phase 4 — Crave's Hit List

| Action | Path | Responsibility |
|---|---|---|
| CREATE | `app/db/models/hitlist_save.py` | HitlistSave model |
| CREATE | `app/db/models/hitlist_suggestion.py` | HitlistSuggestion model |
| CREATE | `app/db/models/hitlist_dedup_key.py` | HitlistDedupKey model |
| MODIFY | `app/db/models/__init__.py` | Register 3 new models |
| CREATE | `alembic/versions/add_hitlist_tables.py` | Migration: create 3 tables |
| CREATE | `app/services/hitlist/__init__.py` | Package init |
| CREATE | `app/services/hitlist/spam_guard.py` | In-memory rate limiter (save + suggest) |
| CREATE | `app/services/hitlist/dedup_engine.py` | Compute dedup key from priority chain |
| CREATE | `app/services/hitlist/save_intake.py` | Save intake: platform detect + dedup + persist |
| CREATE | `app/services/hitlist/suggest_intake.py` | Suggestion intake: rate limit + persist |
| CREATE | `app/services/hitlist/get_user_hitlist.py` | Fetch user's hitlist with filters |
| CREATE | `app/services/hitlist/delete_save.py` | Delete save + dedup key |
| CREATE | `app/services/hitlist/aggregator.py` | Velocity scoring: 70% recency + 30% volume |
| CREATE | `app/services/hitlist/analytics.py` | Analytics: saves_today, top saves, unresolved |
| CREATE | `app/api/v1/schemas/hitlist.py` | Request/response schemas |
| CREATE | `app/api/v1/routes/hitlist.py` | 4 routes + analytics |
| MODIFY | `app/api/v1/routes/__init__.py` | Register hitlist router |
| CREATE | `tests/hitlist/test_dedup_engine.py` | Tests for dedup key computation |
| CREATE | `tests/hitlist/test_save_intake.py` | Tests for save intake + dedup |
| CREATE | `tests/hitlist/test_aggregator.py` | Tests for velocity scoring |
| CREATE | `tests/hitlist/test_hitlist_routes.py` | Integration tests for all routes |

---

## Task 1: signal_context.py — Batch Signal Container

**Files:**
- Create: `app/services/scoring/signal_context.py`
- Create: `tests/scoring/test_place_score_v3.py` (partial — will grow)

- [ ] **Step 1: Write the failing test**

```python
# tests/scoring/test_place_score_v3.py
import pytest
from app.services.scoring.signal_context import SignalContext

def test_signal_context_defaults():
    ctx = SignalContext()
    assert ctx.image_count("unknown-id") == 0
    assert ctx.menu_item_count("unknown-id") == 0
    assert ctx.has_primary_image("unknown-id") is False
    assert ctx.hitlist_score("unknown-id") == 0.0

def test_signal_context_lookup():
    ctx = SignalContext(
        image_counts={"place-1": 5},
        menu_item_counts={"place-1": 30},
        has_primary={"place-1"},
        hitlist_scores={"place-1": 0.75},
    )
    assert ctx.image_count("place-1") == 5
    assert ctx.menu_item_count("place-1") == 30
    assert ctx.has_primary_image("place-1") is True
    assert ctx.hitlist_score("place-1") == 0.75
    # missing place returns safe defaults
    assert ctx.image_count("place-2") == 0
    assert ctx.has_primary_image("place-2") is False
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd /Users/angelowashington/CRAVE/backend
python -m pytest tests/scoring/test_place_score_v3.py -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError: No module named 'app.services.scoring.signal_context'`

- [ ] **Step 3: Implement**

```python
# app/services/scoring/signal_context.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Set

@dataclass
class SignalContext:
    image_counts: Dict[str, int] = field(default_factory=dict)
    menu_item_counts: Dict[str, int] = field(default_factory=dict)
    has_primary: Set[str] = field(default_factory=set)
    hitlist_scores: Dict[str, float] = field(default_factory=dict)

    def image_count(self, place_id: str) -> int:
        return self.image_counts.get(place_id, 0)

    def menu_item_count(self, place_id: str) -> int:
        return self.menu_item_counts.get(place_id, 0)

    def has_primary_image(self, place_id: str) -> bool:
        return place_id in self.has_primary

    def hitlist_score(self, place_id: str) -> float:
        return self.hitlist_scores.get(place_id, 0.0)
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/scoring/test_place_score_v3.py -v
```

Expected: `2 passed`

- [ ] **Step 5: Commit**

```bash
git -C /Users/angelowashington/CRAVE/backend add app/services/scoring/signal_context.py tests/scoring/test_place_score_v3.py
git -C /Users/angelowashington/CRAVE/backend commit -m "feat(scoring): add SignalContext batch signal container"
```

---

## Task 2: city_weight_profiles.py — City-Aware Weights

**Files:**
- Create: `app/services/scoring/city_weight_profiles.py`
- Create: `tests/scoring/test_city_weight_profiles.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/scoring/test_city_weight_profiles.py
import pytest
from app.services.scoring.city_weight_profiles import get_profile, DEFAULT_PROFILE, SIGNALS

def test_default_profile_sums_to_one():
    total = sum(DEFAULT_PROFILE.values())
    assert abs(total - 1.0) < 0.001

def test_default_profile_has_all_signals():
    for signal in SIGNALS:
        assert signal in DEFAULT_PROFILE, f"Missing signal: {signal}"

def test_get_profile_returns_default_for_unknown_city():
    profile = get_profile("atlantis")
    assert profile is DEFAULT_PROFILE

def test_get_profile_returns_default_for_none():
    profile = get_profile(None)
    assert profile is DEFAULT_PROFILE

def test_nyc_profile_sums_to_one():
    profile = get_profile("nyc")
    assert abs(sum(profile.values()) - 1.0) < 0.001

def test_nyc_awards_heavier_than_default():
    nyc = get_profile("nyc")
    assert nyc["awards_score"] > DEFAULT_PROFILE["awards_score"]

def test_la_creator_heavier_than_default():
    la = get_profile("los_angeles")
    assert la["creator_score"] > DEFAULT_PROFILE["creator_score"]

def test_all_city_profiles_sum_to_one():
    from app.services.scoring.city_weight_profiles import CITY_PROFILES
    for slug, profile in CITY_PROFILES.items():
        total = sum(profile.values())
        assert abs(total - 1.0) < 0.001, f"{slug} profile sums to {total}"
```

- [ ] **Step 2: Run to confirm failure**

```bash
python -m pytest tests/scoring/test_city_weight_profiles.py -v 2>&1 | head -10
```

Expected: `ModuleNotFoundError`

- [ ] **Step 3: Implement**

```python
# app/services/scoring/city_weight_profiles.py
from __future__ import annotations
from typing import Dict, Optional

SIGNALS = [
    "menu_score", "image_score", "completeness_score", "recency_score",
    "app_score", "hitlist_score", "creator_score", "awards_score", "blog_score",
]

DEFAULT_PROFILE: Dict[str, float] = {
    "menu_score":         0.22,
    "image_score":        0.18,
    "completeness_score": 0.12,
    "recency_score":      0.10,
    "app_score":          0.13,
    "hitlist_score":      0.10,
    "creator_score":      0.08,
    "awards_score":       0.04,
    "blog_score":         0.03,
}

CITY_PROFILES: Dict[str, Dict[str, float]] = {
    "nyc": {
        "menu_score":         0.18,
        "image_score":        0.14,
        "completeness_score": 0.10,
        "recency_score":      0.08,
        "app_score":          0.10,
        "hitlist_score":      0.10,
        "creator_score":      0.04,
        "awards_score":       0.12,
        "blog_score":         0.14,
    },
    "los_angeles": {
        "menu_score":         0.16,
        "image_score":        0.16,
        "completeness_score": 0.10,
        "recency_score":      0.08,
        "app_score":          0.08,
        "hitlist_score":      0.14,
        "creator_score":      0.16,
        "awards_score":       0.02,
        "blog_score":         0.10,
    },
    "new_orleans": {
        "menu_score":         0.18,
        "image_score":        0.14,
        "completeness_score": 0.10,
        "recency_score":      0.08,
        "app_score":          0.10,
        "hitlist_score":      0.08,
        "creator_score":      0.06,
        "awards_score":       0.08,
        "blog_score":         0.18,
    },
}


def _validate_profile(profile: Dict[str, float], name: str) -> None:
    total = sum(profile.values())
    if abs(total - 1.0) > 0.001:
        raise ValueError(f"Profile '{name}' weights sum to {total:.4f}, must be 1.0")
    for sig in SIGNALS:
        if sig not in profile:
            raise ValueError(f"Profile '{name}' is missing signal '{sig}'")


# Validate at import — fail loud if misconfigured
_validate_profile(DEFAULT_PROFILE, "default")
for _slug, _p in CITY_PROFILES.items():
    _validate_profile(_p, _slug)


def get_profile(city_slug: Optional[str]) -> Dict[str, float]:
    if not city_slug:
        return DEFAULT_PROFILE
    normalized = city_slug.lower().strip().replace(" ", "_").replace("-", "_")
    return CITY_PROFILES.get(normalized, DEFAULT_PROFILE)
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/scoring/test_city_weight_profiles.py -v
```

Expected: `8 passed`

- [ ] **Step 5: Commit**

```bash
git -C /Users/angelowashington/CRAVE/backend add app/services/scoring/city_weight_profiles.py tests/scoring/test_city_weight_profiles.py
git -C /Users/angelowashington/CRAVE/backend commit -m "feat(scoring): add city-aware weight profiles"
```

---

## Task 3: place_score_v3.py — Pure Scoring Function

**Files:**
- Create: `app/services/scoring/place_score_v3.py`
- Modify: `tests/scoring/test_place_score_v3.py`

- [ ] **Step 1: Add tests to existing test file**

Append to `tests/scoring/test_place_score_v3.py`:

```python
from datetime import datetime, timezone, timedelta
from app.services.scoring.place_score_v3 import compute_place_score_v3, _redistribute_weights

def _make_score(
    place_id="abc-123-def-456",
    name="Test Place",
    lat=37.7749, lng=-122.4194,
    has_menu=False, website=None,
    updated_at=None,
    grubhub_url=None, menu_source_url=None,
    image_count=0, has_primary_image=False,
    menu_item_count=0,
    city_slug=None,
):
    return compute_place_score_v3(
        place_id=place_id, name=name, lat=lat, lng=lng,
        has_menu=has_menu, website=website, updated_at=updated_at,
        grubhub_url=grubhub_url, menu_source_url=menu_source_url,
        image_count=image_count, has_primary_image=has_primary_image,
        menu_item_count=menu_item_count, city_slug=city_slug,
    )

def test_empty_place_scores_low():
    result = _make_score()
    assert result.final_score < 0.15

def test_rich_place_scores_higher_than_empty():
    empty = _make_score()
    rich = _make_score(
        has_menu=True, image_count=8, has_primary_image=True,
        menu_item_count=40, grubhub_url="https://grubhub.com/foo",
        updated_at=datetime.now(timezone.utc),
    )
    assert rich.final_score > empty.final_score

def test_score_bounded_0_to_1():
    result = _make_score(
        has_menu=True, image_count=20, has_primary_image=True,
        menu_item_count=100, grubhub_url="https://grubhub.com/foo",
        updated_at=datetime.now(timezone.utc),
    )
    assert 0.0 <= result.final_score <= 1.0

def test_recency_fresh_place():
    now = datetime.now(timezone.utc)
    result = _make_score(updated_at=now)
    assert result.signals["recency_score"] == 1.0

def test_recency_stale_place():
    old = datetime.now(timezone.utc) - timedelta(days=91)
    result = _make_score(updated_at=old)
    assert result.signals["recency_score"] == 0.0

def test_menu_score_normalized():
    result = _make_score(menu_item_count=25)
    assert result.signals["menu_score"] == 0.5

    result_capped = _make_score(menu_item_count=100)
    assert result_capped.signals["menu_score"] == 1.0

def test_image_score_normalized():
    result = _make_score(image_count=5)
    assert result.signals["image_score"] == 0.5

def test_completeness_full():
    result = _make_score(
        name="Joe's Diner", lat=37.7, lng=-122.4,
        has_primary_image=True, has_menu=True,
    )
    assert result.signals["completeness_score"] == 1.0

def test_completeness_empty():
    result = _make_score(name="", lat=None, lng=None,
                         has_primary_image=False, has_menu=False)
    assert result.signals["completeness_score"] == 0.0

def test_deterministic_same_input():
    r1 = _make_score(has_menu=True, image_count=3)
    r2 = _make_score(has_menu=True, image_count=3)
    assert r1.final_score == r2.final_score

def test_uuid_entropy_tiebreak_is_tiny():
    r = _make_score()
    assert r.final_score < 0.000002  # entropy only

def test_redistribute_weights_all_zero():
    weights = {"a": 0.6, "b": 0.4}
    signals = {"a": 0.0, "b": 0.0}
    result = _redistribute_weights(weights, signals)
    # nothing to redistribute to — return original
    assert result == weights

def test_redistribute_weights_one_missing():
    weights = {"a": 0.5, "b": 0.5}
    signals = {"a": 1.0, "b": 0.0}
    result = _redistribute_weights(weights, signals)
    assert abs(result["a"] - 1.0) < 0.001
    assert result["b"] == 0.0
```

- [ ] **Step 2: Run to confirm failures**

```bash
python -m pytest tests/scoring/test_place_score_v3.py -v 2>&1 | head -20
```

Expected: Many failures — `compute_place_score_v3` not yet defined.

- [ ] **Step 3: Implement**

```python
# app/services/scoring/place_score_v3.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Optional

from app.services.scoring.city_weight_profiles import get_profile

_ENTROPY_DIV = 1_000_000_000


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _clamp(v: float) -> float:
    return max(0.0, min(1.0, float(v)))


def _uuid_entropy(place_id: str) -> float:
    try:
        return (int(place_id.replace("-", "")[-6:], 16) % 1_000_000) / _ENTROPY_DIV
    except Exception:
        return 0.0


def _recency(updated_at: Optional[datetime]) -> float:
    if updated_at is None:
        return 0.0
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    days = (_utcnow() - updated_at).total_seconds() / 86400.0
    return _clamp(1.0 - days / 90.0)


def _completeness(
    *,
    name: str,
    lat: Optional[float],
    lng: Optional[float],
    has_image: bool,
    has_menu: bool,
    website: Optional[str],
) -> float:
    checks = [
        bool((name or "").strip()),
        lat is not None and lng is not None,
        has_image,
        has_menu or bool((website or "").strip()),
    ]
    return sum(checks) / len(checks)


def _redistribute_weights(
    weights: Dict[str, float],
    signals: Dict[str, float],
) -> Dict[str, float]:
    has_data = {k for k, v in signals.items() if v > 0.0}
    if not has_data:
        return weights
    missing_weight = sum(weights[k] for k in weights if k not in has_data)
    if missing_weight == 0.0:
        return weights
    active_total = sum(weights[k] for k in has_data)
    if active_total == 0.0:
        return weights
    result = {}
    for k, w in weights.items():
        if k in has_data:
            result[k] = w + (w / active_total) * missing_weight
        else:
            result[k] = 0.0
    return result


@dataclass(frozen=True)
class ScoreV3Result:
    final_score: float
    signals: Dict[str, float]
    weights_used: Dict[str, float]
    city_slug: Optional[str]
    computed_at: datetime


def compute_place_score_v3(
    *,
    place_id: str,
    name: str,
    lat: Optional[float],
    lng: Optional[float],
    has_menu: bool,
    website: Optional[str],
    updated_at: Optional[datetime],
    grubhub_url: Optional[str],
    menu_source_url: Optional[str],
    image_count: int,
    has_primary_image: bool,
    menu_item_count: int,
    hitlist_score: float = 0.0,
    creator_score: float = 0.0,
    awards_score: float = 0.0,
    blog_score: float = 0.0,
    city_slug: Optional[str] = None,
) -> ScoreV3Result:
    signals: Dict[str, float] = {
        "menu_score":         _clamp(min(menu_item_count / 50.0, 1.0)),
        "image_score":        _clamp(min(image_count / 10.0, 1.0)),
        "completeness_score": _completeness(
            name=name, lat=lat, lng=lng,
            has_image=has_primary_image,
            has_menu=has_menu, website=website,
        ),
        "recency_score":      _recency(updated_at),
        "app_score":          1.0 if (grubhub_url or menu_source_url) else 0.0,
        "hitlist_score":      _clamp(hitlist_score),
        "creator_score":      _clamp(creator_score),
        "awards_score":       _clamp(awards_score),
        "blog_score":         _clamp(blog_score),
    }

    weights = get_profile(city_slug)
    weights_used = _redistribute_weights(weights, signals)
    final_score = _clamp(sum(signals[k] * weights_used[k] for k in weights_used))
    final_score += _uuid_entropy(place_id)

    return ScoreV3Result(
        final_score=round(final_score, 6),
        signals=signals,
        weights_used=weights_used,
        city_slug=city_slug,
        computed_at=_utcnow(),
    )
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/scoring/test_place_score_v3.py -v
```

Expected: `all tests pass`

- [ ] **Step 5: Commit**

```bash
git -C /Users/angelowashington/CRAVE/backend add app/services/scoring/place_score_v3.py tests/scoring/test_place_score_v3.py
git -C /Users/angelowashington/CRAVE/backend commit -m "feat(scoring): add place_score_v3 pure scoring function with 9 signals"
```

---

## Task 4: Wire v3 into recompute_scores_worker.py

**Files:**
- Modify: `app/workers/recompute_scores_worker.py`

- [ ] **Step 1: Read current file to understand structure**

```bash
cat /Users/angelowashington/CRAVE/backend/app/workers/recompute_scores_worker.py
```

- [ ] **Step 2: Replace the file with the updated version**

```python
# app/workers/recompute_scores_worker.py
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.db.models.place import Place
from app.db.models.place_image import PlaceImage
from app.db.models.menu_item import MenuItem
from app.services.scoring.signal_context import SignalContext
from app.services.scoring.place_score_v3 import compute_place_score_v3

BASE_DIR = Path(__file__).resolve().parents[2]
QUEUE_FILE = BASE_DIR / "var" / "queue" / "recompute_scores.queue"


@dataclass(frozen=True)
class Job:
    type: str
    created_at: str
    payload: Dict[str, Any]


def _read_jobs() -> list[Job]:
    if not QUEUE_FILE.exists():
        return []
    raw = QUEUE_FILE.read_text(encoding="utf-8").strip()
    if not raw:
        return []
    return [
        Job(
            type=str(d.get("type")),
            created_at=str(d.get("created_at")),
            payload=dict(d.get("payload") or {}),
        )
        for d in (json.loads(line) for line in raw.splitlines())
    ]


def _clear_queue() -> None:
    QUEUE_FILE.write_text("", encoding="utf-8")


def _fetch_signal_context(db: Session, place_ids: list[str]) -> SignalContext:
    """Batch-fetch all signal data. One query per signal type — never per-place."""
    if not place_ids:
        return SignalContext()

    # Image counts per place
    image_rows = db.execute(
        select(PlaceImage.place_id, func.count(PlaceImage.id).label("cnt"))
        .where(PlaceImage.place_id.in_(place_ids))
        .group_by(PlaceImage.place_id)
    ).all()
    image_counts = {r.place_id: r.cnt for r in image_rows}

    # Places with a primary image
    primary_rows = db.execute(
        select(PlaceImage.place_id)
        .where(
            PlaceImage.place_id.in_(place_ids),
            PlaceImage.is_primary.is_(True),
        )
    ).all()
    has_primary = {r.place_id for r in primary_rows}

    # Active menu item counts per place
    menu_rows = db.execute(
        select(MenuItem.place_id, func.count(MenuItem.id).label("cnt"))
        .where(
            MenuItem.place_id.in_(place_ids),
            MenuItem.is_active.is_(True),
        )
        .group_by(MenuItem.place_id)
    ).all()
    menu_counts = {r.place_id: r.cnt for r in menu_rows}

    return SignalContext(
        image_counts=image_counts,
        has_primary=has_primary,
        menu_item_counts=menu_counts,
    )


def _clamp_limit(limit: Optional[int]) -> Optional[int]:
    if limit is None:
        return None
    try:
        return max(1, int(limit))
    except Exception:
        return None


def _iter_place_batches(
    db: Session,
    *,
    city_id: Optional[str],
    limit: Optional[int],
    batch_size: int = 500,
):
    limit = _clamp_limit(limit)
    stmt = select(Place).order_by(Place.id.asc())
    if city_id:
        stmt = stmt.where(Place.city_id == city_id)

    offset = 0
    processed = 0

    while True:
        batch = db.execute(stmt.limit(batch_size).offset(offset)).scalars().all()
        if not batch:
            break
        if limit is not None:
            remaining = limit - processed
            if remaining <= 0:
                break
            batch = batch[:remaining]

        yield batch
        processed += len(batch)
        offset += batch_size
        if limit is not None and processed >= limit:
            break


def _score_batch(db: Session, places: list[Place]) -> int:
    place_ids = [p.id for p in places]
    ctx = _fetch_signal_context(db, place_ids)

    now = datetime.now(timezone.utc)
    updated = 0

    for place in places:
        pid = place.id

        # Resolve city slug for city-aware weights
        city_slug: Optional[str] = None
        city = getattr(place, "city", None)
        if city:
            city_slug = getattr(city, "slug", None) or getattr(city, "name", None)

        result = compute_place_score_v3(
            place_id=pid,
            name=place.name or "",
            lat=place.lat,
            lng=place.lng,
            has_menu=bool(place.has_menu),
            website=place.website,
            updated_at=place.updated_at,
            grubhub_url=place.grubhub_url,
            menu_source_url=place.menu_source_url,
            image_count=ctx.image_count(pid),
            has_primary_image=ctx.has_primary_image(pid),
            menu_item_count=ctx.menu_item_count(pid),
            hitlist_score=ctx.hitlist_score(pid),
            city_slug=city_slug,
        )

        place.master_score = result.final_score
        place.rank_score = result.final_score
        place.last_scored_at = now
        updated += 1

    return updated


def run_worker_once() -> int:
    jobs = _read_jobs()
    if not jobs:
        return 0

    _clear_queue()
    db = SessionLocal()
    total_updated = 0

    try:
        for job in jobs:
            if job.type != "recompute_scores":
                continue

            city_id = job.payload.get("city_id")
            limit = job.payload.get("limit")

            for batch in _iter_place_batches(db, city_id=city_id, limit=limit):
                updated = _score_batch(db, batch)
                total_updated += updated
                db.commit()

        return total_updated

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()
```

- [ ] **Step 3: Verify existing server starts cleanly**

```bash
cd /Users/angelowashington/CRAVE/backend
python -c "from app.workers.recompute_scores_worker import run_worker_once; print('import ok')"
```

Expected: `import ok`

- [ ] **Step 4: Run full scoring test suite**

```bash
python -m pytest tests/scoring/ -v
```

Expected: all pass

- [ ] **Step 5: Commit**

```bash
git -C /Users/angelowashington/CRAVE/backend add app/workers/recompute_scores_worker.py
git -C /Users/angelowashington/CRAVE/backend commit -m "feat(scoring): wire place_score_v3 into recompute worker with batch signal fetch"
```

---

## Task 5: Mapbox GeoJSON Schemas

**Files:**
- Modify: `app/api/v1/schemas/map.py`
- Create: `tests/map/test_map_geojson.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/map/test_map_geojson.py
import pytest
from app.api.v1.schemas.map import GeoJSONFeatureCollection, GeoJSONFeature, GeoJSONGeometry, GeoJSONProperties

def test_geojson_feature_collection_structure():
    fc = GeoJSONFeatureCollection(features=[
        GeoJSONFeature(
            geometry=GeoJSONGeometry(coordinates=[-122.41, 37.77]),
            properties=GeoJSONProperties(
                id="abc", name="Test", tier="elite",
                rank_score=0.85, price_tier=2,
                primary_image_url=None, has_menu=True,
            ),
        )
    ])
    assert fc.type == "FeatureCollection"
    assert len(fc.features) == 1
    assert fc.features[0].type == "Feature"
    assert fc.features[0].geometry.type == "Point"
    assert fc.features[0].geometry.coordinates == [-122.41, 37.77]
    assert fc.features[0].properties.tier == "elite"

def test_geojson_properties_tier_values():
    for tier in ("elite", "trusted", "solid", "default"):
        props = GeoJSONProperties(
            id="x", name="X", tier=tier, rank_score=0.5,
        )
        assert props.tier == tier
```

- [ ] **Step 2: Run to confirm failure**

```bash
python -m pytest tests/map/test_map_geojson.py -v 2>&1 | head -15
```

Expected: `ImportError` — schemas don't exist yet.

- [ ] **Step 3: Append to `app/api/v1/schemas/map.py`**

Add at the end of the existing file:

```python
# --- GeoJSON types (Mapbox FeatureCollection) ---

from typing import Any

class GeoJSONProperties(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: str
    name: str
    tier: str  # elite | trusted | solid | default
    rank_score: float = Field(..., ge=0.0)
    price_tier: Optional[int] = Field(default=None, ge=1, le=4)
    primary_image_url: Optional[str] = None
    has_menu: bool = False


class GeoJSONGeometry(BaseModel):
    model_config = ConfigDict(frozen=True)
    type: str = "Point"
    coordinates: list[float]  # [lng, lat] — Mapbox standard


class GeoJSONFeature(BaseModel):
    model_config = ConfigDict(frozen=True)
    type: str = "Feature"
    geometry: GeoJSONGeometry
    properties: GeoJSONProperties


class GeoJSONFeatureCollection(BaseModel):
    model_config = ConfigDict(frozen=True)
    type: str = "FeatureCollection"
    features: list[GeoJSONFeature]
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/map/test_map_geojson.py -v
```

Expected: `2 passed`

- [ ] **Step 5: Commit**

```bash
git -C /Users/angelowashington/CRAVE/backend add app/api/v1/schemas/map.py tests/map/test_map_geojson.py
git -C /Users/angelowashington/CRAVE/backend commit -m "feat(map): add GeoJSON schema types for Mapbox FeatureCollection"
```

---

## Task 6: Mapbox GeoJSON Query + Route

**Files:**
- Modify: `app/services/query/map_query.py`
- Modify: `app/api/v1/routes/map.py`
- Modify: `tests/map/test_map_geojson.py`

- [ ] **Step 1: Add tier logic tests**

Append to `tests/map/test_map_geojson.py`:

```python
from app.services.query.map_query import _compute_tier_thresholds, _assign_tier

def test_tier_thresholds_empty():
    t = _compute_tier_thresholds([])
    # anything returns default when no scores
    assert _assign_tier(0.99, t) == "default"

def test_tier_percentile_ordering():
    scores = list(range(100))  # 0–99
    t = _compute_tier_thresholds([float(s) for s in scores])
    # top 5% = score >= 95
    assert _assign_tier(95.0, t) == "elite"
    assert _assign_tier(85.0, t) == "trusted"
    assert _assign_tier(55.0, t) == "solid"
    assert _assign_tier(20.0, t) == "default"

def test_tier_single_score():
    t = _compute_tier_thresholds([0.5])
    # only one score — it's both elite and everything
    assert _assign_tier(0.5, t) == "elite"
```

- [ ] **Step 2: Run to confirm failure**

```bash
python -m pytest tests/map/test_map_geojson.py::test_tier_percentile_ordering -v 2>&1 | head -10
```

Expected: `ImportError`

- [ ] **Step 3: Append tier helpers to `app/services/query/map_query.py`**

Add at the end of the existing file (after the `get_map_places` alias):

```python
# --- GeoJSON / Mapbox support ---

def _compute_tier_thresholds(scores: list[float]) -> dict:
    """
    Compute percentile-based tier thresholds from the scores in this result set.
    elite = top 5%, trusted = next 15%, solid = next 30%, default = bottom 50%.
    Uses the result set — not global DB — so map always has good color distribution.
    """
    if not scores:
        # No scores: return sentinels that make everything "default"
        return {"elite": float("inf"), "trusted": float("inf"), "solid": float("inf")}

    sorted_scores = sorted(scores)
    n = len(sorted_scores)

    elite_idx  = max(0, int(n * 0.95))
    trusted_idx = max(0, int(n * 0.80))
    solid_idx  = max(0, int(n * 0.50))

    return {
        "elite":   sorted_scores[elite_idx],
        "trusted": sorted_scores[trusted_idx],
        "solid":   sorted_scores[solid_idx],
    }


def _assign_tier(score: float, thresholds: dict) -> str:
    if score >= thresholds["elite"]:
        return "elite"
    if score >= thresholds["trusted"]:
        return "trusted"
    if score >= thresholds["solid"]:
        return "solid"
    return "default"


def fetch_places_for_map_geojson(
    db,
    *,
    lat: float,
    lng: float,
    radius_km: float = DEFAULT_RADIUS_KM,
    limit: int = DEFAULT_LIMIT,
    city_id=None,
    category_id=None,
) -> dict:
    """
    Returns a Mapbox-compatible GeoJSON FeatureCollection.
    Wraps fetch_places_for_map — same query, same cache eligibility.
    Tiers are percentile-based within this result set.
    """
    result = fetch_places_for_map(
        db=db, lat=lat, lng=lng, radius_km=radius_km,
        limit=limit, city_id=city_id, category_id=category_id,
    )
    places = result.get("places", [])
    scores = [p["rank_score"] for p in places]
    thresholds = _compute_tier_thresholds(scores)

    features = []
    for p in places:
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [p["lng"], p["lat"]],
            },
            "properties": {
                "id": p["id"],
                "name": p["name"],
                "tier": _assign_tier(p["rank_score"], thresholds),
                "rank_score": p["rank_score"],
                "price_tier": p.get("price_tier"),
                "primary_image_url": p.get("primary_image_url"),
                "has_menu": False,
            },
        })

    return {"type": "FeatureCollection", "features": features}
```

- [ ] **Step 4: Add `/map/geojson` route to `app/api/v1/routes/map.py`**

Add after the existing `map_places` route:

```python
from app.services.query.map_query import fetch_places_for_map_geojson
from app.api.v1.schemas.map import GeoJSONFeatureCollection

@router.get(
    "/geojson",
    response_model=GeoJSONFeatureCollection,
    summary="Get places as Mapbox GeoJSON FeatureCollection",
)
def map_places_geojson(
    lat: float = Query(..., description="Latitude"),
    lng: float = Query(..., description="Longitude"),
    radius_km: float = Query(DEFAULT_RADIUS_KM, ge=0.1, le=50.0),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    city_id: Optional[str] = Query(None),
    category_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> GeoJSONFeatureCollection:

    lat_v = _safe_float(lat)
    lng_v = _safe_float(lng)
    if lat_v is None or lng_v is None:
        return GeoJSONFeatureCollection(features=[])

    cache_key = map_key(
        lat=lat_v, lng=lng_v, radius_km=radius_km,
        limit=limit, city_id=city_id, category_id=category_id,
    ) + ":geojson"

    cached = response_cache.get(cache_key)
    if cached is not None:
        try:
            return GeoJSONFeatureCollection.model_validate(cached)
        except Exception:
            pass

    try:
        result = fetch_places_for_map_geojson(
            db=db, lat=lat_v, lng=lng_v, radius_km=radius_km,
            limit=_clamp_limit(limit), city_id=_clean_str(city_id),
            category_id=_clean_str(category_id),
        )
        payload = GeoJSONFeatureCollection.model_validate(result)
    except Exception as exc:
        logger.error("map_geojson_failed lat=%s lng=%s error=%s", lat_v, lng_v, exc)
        return GeoJSONFeatureCollection(features=[])

    try:
        response_cache.set(cache_key, payload.model_dump(), map_ttl(radius_km=radius_km))
    except Exception:
        pass

    return payload
```

- [ ] **Step 5: Run map tests**

```bash
python -m pytest tests/map/ -v
```

Expected: all pass

- [ ] **Step 6: Verify server starts**

```bash
python -c "from app.api.v1.routes.map import router; print('map router ok')"
```

- [ ] **Step 7: Commit**

```bash
git -C /Users/angelowashington/CRAVE/backend add app/services/query/map_query.py app/api/v1/routes/map.py tests/map/
git -C /Users/angelowashington/CRAVE/backend commit -m "feat(map): add /map/geojson endpoint with percentile-based Mapbox tiers"
```

---

## Task 7: Social Layer — platform_detect + url_normalize

**Files:**
- Create: `app/services/social/__init__.py`
- Create: `app/services/social/platform_detect.py`
- Create: `app/services/social/url_normalize.py`
- Create: `tests/social/test_platform_detect.py`
- Create: `tests/social/test_url_normalize.py`

- [ ] **Step 1: Write tests**

```python
# tests/social/test_platform_detect.py
import pytest
from app.services.social.platform_detect import detect_platform

@pytest.mark.parametrize("url,expected", [
    ("https://www.tiktok.com/@foodie/video/123", "tiktok"),
    ("https://vm.tiktok.com/ZMxyz/", "tiktok"),
    ("https://www.instagram.com/p/abc123/", "instagram"),
    ("https://www.youtube.com/watch?v=abc", "youtube"),
    ("https://youtu.be/abc", "youtube"),
    ("https://www.facebook.com/joespizza", "facebook"),
    ("https://fb.com/joespizza", "facebook"),
    ("https://maps.google.com/?q=...", "google_maps"),
    ("https://goo.gl/maps/abc", "google_maps"),
    ("https://www.yelp.com/biz/joes-pizza", "yelp"),
    ("https://www.grubhub.com/restaurant/...", "grubhub"),
    ("https://www.doordash.com/store/...", "doordash"),
    ("https://www.ubereats.com/store/...", "ubereats"),
    ("https://www.joespizza.com/menu", "generic"),
    (None, "unknown"),
    ("", "unknown"),
    ("not a url", "generic"),
])
def test_detect_platform(url, expected):
    assert detect_platform(url) == expected
```

```python
# tests/social/test_url_normalize.py
import pytest
from app.services.social.url_normalize import normalize_url

def test_strips_utm_params():
    url = "https://www.tiktok.com/@user/video/123?utm_source=copy&utm_medium=android"
    result = normalize_url(url)
    assert "utm_source" not in result
    assert "utm_medium" not in result
    assert "@user/video/123" in result

def test_strips_fbclid():
    url = "https://www.facebook.com/foo?fbclid=IwAbc123"
    result = normalize_url(url)
    assert "fbclid" not in result

def test_strips_igshid():
    url = "https://www.instagram.com/p/abc/?igshid=xyz"
    result = normalize_url(url)
    assert "igshid" not in result

def test_lowercases_host():
    url = "https://WWW.TIKTOK.COM/@user/video/123"
    result = normalize_url(url)
    assert "www.tiktok.com" in result

def test_removes_trailing_slash():
    url = "https://www.tiktok.com/@user/"
    result = normalize_url(url)
    assert result.endswith("@user")

def test_none_returns_none():
    assert normalize_url(None) is None

def test_empty_returns_none():
    assert normalize_url("") is None

def test_preserves_non_tracking_params():
    url = "https://example.com/menu?category=pizza&size=large"
    result = normalize_url(url)
    assert "category=pizza" in result
    assert "size=large" in result
```

- [ ] **Step 2: Run to confirm failure**

```bash
python -m pytest tests/social/ -v 2>&1 | head -10
```

- [ ] **Step 3: Implement**

```python
# app/services/social/__init__.py
```

```python
# app/services/social/platform_detect.py
from __future__ import annotations


def detect_platform(url: str | None) -> str:
    if not url:
        return "unknown"
    u = url.lower()
    if "tiktok.com" in u:
        return "tiktok"
    if "instagram.com" in u:
        return "instagram"
    if "youtube.com" in u or "youtu.be" in u:
        return "youtube"
    if "facebook.com" in u or "fb.com" in u:
        return "facebook"
    if "maps.google" in u or "goo.gl/maps" in u:
        return "google_maps"
    if "yelp.com" in u:
        return "yelp"
    if "grubhub.com" in u:
        return "grubhub"
    if "doordash.com" in u:
        return "doordash"
    if "ubereats.com" in u:
        return "ubereats"
    if "opentable.com" in u:
        return "opentable"
    if "resy.com" in u:
        return "resy"
    if url.startswith("http"):
        return "generic"
    return "generic"
```

```python
# app/services/social/url_normalize.py
from __future__ import annotations
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

_TRACKING = frozenset({
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "utm_id", "utm_name", "utm_reader", "utm_viz_id", "utm_pubreferrer",
    "utm_swu", "fbclid", "gclid", "igshid", "mc_cid", "mc_eid",
    "ref", "s",
})


def normalize_url(url: str | None) -> str | None:
    if not url or not url.strip():
        return None
    try:
        p = urlparse(url.strip())
        netloc = p.netloc.lower()
        path = p.path.rstrip("/")
        pairs = [
            (k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
            if k.lower() not in _TRACKING
        ]
        result = urlunparse((p.scheme.lower(), netloc, path, p.params, urlencode(pairs), ""))
        return result or None
    except Exception:
        return url
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/social/test_platform_detect.py tests/social/test_url_normalize.py -v
```

Expected: all pass

- [ ] **Step 5: Commit**

```bash
git -C /Users/angelowashington/CRAVE/backend add app/services/social/ tests/social/
git -C /Users/angelowashington/CRAVE/backend commit -m "feat(social): add platform_detect and url_normalize"
```

---

## Task 8: Social Layer — caption_parser + extractors

**Files:**
- Create: `app/services/social/caption_parser.py`
- Create: `app/services/social/extractors/__init__.py`
- Create: `app/services/social/extractors/tiktok.py`
- Create: `app/services/social/extractors/instagram.py`
- Create: `app/services/social/extractors/youtube.py`
- Create: `tests/social/test_caption_parser.py`
- Create: `tests/social/test_extractors.py`

- [ ] **Step 1: Write tests**

```python
# tests/social/test_caption_parser.py
import pytest
from app.services.social.caption_parser import parse_caption

def test_empty_text_returns_empty():
    result = parse_caption("")
    assert result.hashtags == []
    assert result.place_candidates == []

def test_extracts_hashtags():
    result = parse_caption("Great food! #foodie #bayarea #eats")
    assert "foodie" in result.hashtags
    assert "bayarea" in result.hashtags

def test_extracts_location_line():
    result = parse_caption("📍 Joe's Tacos\nSo good!")
    assert "Joe's Tacos" in result.location_lines
    assert "Joe's Tacos" in result.place_candidates

def test_extracts_at_pattern():
    result = parse_caption("Had the best burger at Joe's Diner last night")
    assert any("Joe" in c for c in result.place_candidates)

def test_extracts_geo_hints_city_state():
    result = parse_caption("Best pizza in Oakland, CA!")
    assert any("Oakland" in h for h in result.geo_hints)

def test_has_food_terms():
    result = parse_caption("This restaurant has the best menu")
    assert result.has_food_terms is True

def test_no_food_terms():
    result = parse_caption("Look at this cool car show")
    assert result.has_food_terms is False

def test_none_input():
    result = parse_caption(None)
    assert result.hashtags == []

def test_to_dict_has_all_keys():
    result = parse_caption("test").to_dict()
    for key in ("hashtags", "mentions", "location_lines", "place_candidates", "geo_hints", "has_food_terms"):
        assert key in result
```

```python
# tests/social/test_extractors.py
import pytest
from app.services.social.extractors.tiktok import extract_from_tiktok
from app.services.social.extractors.instagram import extract_from_instagram
from app.services.social.extractors.youtube import extract_from_youtube

# TikTok
def test_tiktok_extracts_handle():
    result = extract_from_tiktok("https://www.tiktok.com/@foodie_la/video/7123456789")
    assert result["creator_handle"] == "foodie_la"
    assert result["confidence"] == 0.40
    assert result["platform"] == "tiktok"

def test_tiktok_no_handle():
    result = extract_from_tiktok("https://vm.tiktok.com/ZMxyz/")
    assert result["creator_handle"] is None
    assert result["confidence"] == 0.0

def test_tiktok_bad_url():
    result = extract_from_tiktok("not a url")
    assert result["platform"] == "tiktok"
    assert result["confidence"] == 0.0

# Instagram
def test_instagram_extracts_handle():
    result = extract_from_instagram("https://www.instagram.com/joespizza/")
    assert result["creator_handle"] == "joespizza"
    assert result["confidence"] == 0.35

def test_instagram_post_no_handle():
    result = extract_from_instagram("https://www.instagram.com/p/CxyzABC/")
    assert result["creator_handle"] is None

# YouTube
def test_youtube_at_handle():
    result = extract_from_youtube("https://www.youtube.com/@FoodChannel")
    assert result["creator_handle"] == "FoodChannel"
    assert result["confidence"] == 0.30

def test_youtube_c_handle():
    result = extract_from_youtube("https://www.youtube.com/c/FoodChannel")
    assert result["creator_handle"] == "FoodChannel"

def test_youtube_no_handle():
    result = extract_from_youtube("https://www.youtube.com/watch?v=abc123")
    assert result["creator_handle"] is None
    assert result["confidence"] == 0.0

# All return correct contract keys
@pytest.mark.parametrize("fn,url", [
    (extract_from_tiktok, "https://tiktok.com/@x"),
    (extract_from_instagram, "https://instagram.com/x"),
    (extract_from_youtube, "https://youtube.com/@x"),
])
def test_extractor_contract(fn, url):
    result = fn(url)
    for key in ("platform", "creator_handle", "confidence", "source_url", "place_name_hint"):
        assert key in result
```

- [ ] **Step 2: Run to confirm failure**

```bash
python -m pytest tests/social/test_caption_parser.py tests/social/test_extractors.py -v 2>&1 | head -10
```

- [ ] **Step 3: Implement caption_parser.py**

```python
# app/services/social/caption_parser.py
from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Optional

_RE_HASHTAG = re.compile(r"#([A-Za-z0-9_]{2,})")
_RE_MENTION = re.compile(r"@([A-Za-z0-9._]{1,})")
_RE_LOC_LINE = re.compile(r"(?im)^(?:\s*(?:📍|location\s*[:\-]|loc\s*[:\-])\s*)(.+?)\s*$")
_RE_AT_IN = re.compile(r"(?i)\b(?:at|in)\s+([A-Za-z0-9][A-Za-z0-9'&\.\-\s]{2,60})")
_RE_CITY_ST = re.compile(r"\b([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+){0,2})\s*,\s*([A-Z]{2})\b")
_RE_TRIM = re.compile(r"[\s\-\|•·:]+$")
_JUNK = frozenset({"tiktok", "instagram", "youtube", "reel", "shorts", "fyp", "foryou"})
_FOOD = frozenset({"food", "menu", "dish", "eat", "restaurant", "cafe", "diner", "brunch", "lunch", "dinner"})
_GEO_TAGS = frozenset({"oakland", "sf", "sanfrancisco", "bayarea", "sanjose", "la", "losangeles",
                        "nyc", "newyork", "chicago", "houston", "phoenix", "seattle", "portland"})


def _clean(s: str) -> Optional[str]:
    s = re.sub(r"\s+", " ", (s or "").strip())
    s = _RE_TRIM.sub("", s).strip()
    if not s or len(s) < 3 or len(s) > 80:
        return None
    if s.lower() in _JUNK or re.fullmatch(r"[\W_]+", s):
        return None
    return s


@dataclass(frozen=True)
class CaptionSignals:
    hashtags: list[str] = field(default_factory=list)
    mentions: list[str] = field(default_factory=list)
    location_lines: list[str] = field(default_factory=list)
    place_candidates: list[str] = field(default_factory=list)
    geo_hints: list[str] = field(default_factory=list)
    has_food_terms: bool = False

    def to_dict(self) -> dict:
        return {
            "hashtags": self.hashtags,
            "mentions": self.mentions,
            "location_lines": self.location_lines,
            "place_candidates": self.place_candidates,
            "geo_hints": self.geo_hints,
            "has_food_terms": self.has_food_terms,
        }


def parse_caption(text: str | None) -> CaptionSignals:
    text = (text or "").strip()
    if not text:
        return CaptionSignals()

    hashtags = [m.group(1) for m in _RE_HASHTAG.finditer(text)][:25]
    mentions = [m.group(1) for m in _RE_MENTION.finditer(text)][:10]

    loc_lines = []
    for m in _RE_LOC_LINE.finditer(text):
        c = _clean(m.group(1))
        if c and c not in loc_lines:
            loc_lines.append(c)

    geo_hints = []
    for m in _RE_CITY_ST.finditer(text):
        h = f"{m.group(1).strip()}, {m.group(2).strip()}"
        if h not in geo_hints:
            geo_hints.append(h)
    for tag in hashtags:
        if tag.lower() in _GEO_TAGS and tag not in geo_hints:
            geo_hints.append(tag)

    candidates = list(loc_lines)
    for m in _RE_AT_IN.finditer(text):
        c = _clean(m.group(1))
        if not c:
            continue
        c = re.split(r"\b(?:for|with|and|but|because|when|where)\b", c, 1, re.IGNORECASE)[0].strip()
        c = _clean(c)
        if c and c not in candidates:
            candidates.append(c)

    has_food = bool(_FOOD.intersection(text.lower().split()))

    return CaptionSignals(
        hashtags=hashtags,
        mentions=mentions,
        location_lines=loc_lines,
        place_candidates=candidates[:10],
        geo_hints=geo_hints,
        has_food_terms=has_food,
    )
```

- [ ] **Step 4: Implement extractors**

```python
# app/services/social/extractors/__init__.py
```

```python
# app/services/social/extractors/tiktok.py
from __future__ import annotations
import re
from urllib.parse import urlparse

_HANDLE = re.compile(r"^@?([a-zA-Z0-9._]{1,64})$")


def extract_from_tiktok(url: str) -> dict:
    try:
        path = (urlparse(url).path or "").strip()
        handle = None
        for part in path.split("/"):
            if part.startswith("@"):
                m = _HANDLE.match(part[1:])
                if m:
                    handle = m.group(1)
                    break
        return {"platform": "tiktok", "creator_handle": handle,
                "confidence": 0.40 if handle else 0.0,
                "source_url": url, "place_name_hint": None}
    except Exception:
        return {"platform": "tiktok", "creator_handle": None,
                "confidence": 0.0, "source_url": url, "place_name_hint": None}
```

```python
# app/services/social/extractors/instagram.py
from __future__ import annotations
import re
from urllib.parse import urlparse

_HANDLE = re.compile(r"^([a-zA-Z0-9._]{1,30})$")
_RESERVED = frozenset({"p", "reel", "explore", "stories", "tv", "direct", "accounts"})


def extract_from_instagram(url: str) -> dict:
    try:
        parts = [p for p in (urlparse(url).path or "").split("/") if p]
        handle = None
        if parts and parts[0] not in _RESERVED:
            m = _HANDLE.match(parts[0])
            if m:
                handle = m.group(1)
        return {"platform": "instagram", "creator_handle": handle,
                "confidence": 0.35 if handle else 0.0,
                "source_url": url, "place_name_hint": None}
    except Exception:
        return {"platform": "instagram", "creator_handle": None,
                "confidence": 0.0, "source_url": url, "place_name_hint": None}
```

```python
# app/services/social/extractors/youtube.py
from __future__ import annotations
from urllib.parse import urlparse


def extract_from_youtube(url: str) -> dict:
    try:
        parts = [p for p in (urlparse(url).path or "").split("/") if p]
        handle = None
        if parts:
            if parts[0].startswith("@"):
                handle = parts[0][1:] or None
            elif parts[0] in {"c", "user"} and len(parts) > 1:
                handle = parts[1]
        return {"platform": "youtube", "creator_handle": handle,
                "confidence": 0.30 if handle else 0.0,
                "source_url": url, "place_name_hint": None}
    except Exception:
        return {"platform": "youtube", "creator_handle": None,
                "confidence": 0.0, "source_url": url, "place_name_hint": None}
```

- [ ] **Step 5: Run all social tests**

```bash
python -m pytest tests/social/ -v
```

Expected: all pass

- [ ] **Step 6: Commit**

```bash
git -C /Users/angelowashington/CRAVE/backend add app/services/social/ tests/social/
git -C /Users/angelowashington/CRAVE/backend commit -m "feat(social): add caption_parser and TikTok/Instagram/YouTube extractors"
```

---

## Task 9: Hit List DB Models

**Files:**
- Create: `app/db/models/hitlist_save.py`
- Create: `app/db/models/hitlist_suggestion.py`
- Create: `app/db/models/hitlist_dedup_key.py`
- Modify: `app/db/models/__init__.py`

- [ ] **Step 1: Create hitlist_save.py**

```python
# app/db/models/hitlist_save.py
from __future__ import annotations
import uuid
from datetime import datetime
from sqlalchemy import DateTime, Float, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db.models.base import Base, TimestampMixin


class HitlistSave(Base, TimestampMixin):
    __tablename__ = "hitlist_saves"
    __table_args__ = (
        UniqueConstraint("user_id", "dedup_key", name="uq_hitlist_saves_user_dedup"),
        Index("ix_hitlist_saves_user_created", "user_id", "created_at"),
        Index("ix_hitlist_saves_place_id", "place_id"),
        Index("ix_hitlist_saves_status", "resolution_status"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    place_name: Mapped[str] = mapped_column(String(256), nullable=False)
    source_platform: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    place_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("places.id", ondelete="SET NULL"), nullable=True
    )
    resolution_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="raw", index=True
    )
    # resolution_status values: raw | candidate | matched | promoted | rejected
    dedup_key: Mapped[str] = mapped_column(String(128), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
```

- [ ] **Step 2: Create hitlist_suggestion.py**

```python
# app/db/models/hitlist_suggestion.py
from __future__ import annotations
import uuid
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.db.models.base import Base, TimestampMixin


class HitlistSuggestion(Base, TimestampMixin):
    __tablename__ = "hitlist_suggestions"
    __table_args__ = (
        Index("ix_hitlist_suggestions_user_created", "user_id", "created_at"),
        Index("ix_hitlist_suggestions_name_city", "place_name", "city_hint"),
        Index("ix_hitlist_suggestions_resolved_place", "resolved_place_id"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    place_name: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    city_hint: Mapped[str | None] = mapped_column(String(128), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_platform: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    resolved_place_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("places.id", ondelete="SET NULL"), nullable=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
```

- [ ] **Step 3: Create hitlist_dedup_key.py**

```python
# app/db/models/hitlist_dedup_key.py
from __future__ import annotations
import uuid
from sqlalchemy import Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db.models.base import Base, TimestampMixin


class HitlistDedupKey(Base, TimestampMixin):
    __tablename__ = "hitlist_dedup_keys"
    __table_args__ = (
        UniqueConstraint("user_id", "dedup_key", name="uq_hitlist_dedup_keys_user_key"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    dedup_key: Mapped[str] = mapped_column(String(128), nullable=False)
```

- [ ] **Step 4: Register models in `app/db/models/__init__.py`**

Add after the `# ----- Ranking Layer -----` block:

```python
# ----- Hit List Layer -----
from .hitlist_save import HitlistSave
from .hitlist_suggestion import HitlistSuggestion
from .hitlist_dedup_key import HitlistDedupKey
```

And add to `__all__`:

```python
    # Hit List
    "HitlistSave",
    "HitlistSuggestion",
    "HitlistDedupKey",
```

- [ ] **Step 5: Verify models import cleanly**

```bash
python -c "from app.db.models import HitlistSave, HitlistSuggestion, HitlistDedupKey; print('hitlist models ok')"
```

Expected: `hitlist models ok`

- [ ] **Step 6: Commit**

```bash
git -C /Users/angelowashington/CRAVE/backend add app/db/models/hitlist_save.py app/db/models/hitlist_suggestion.py app/db/models/hitlist_dedup_key.py app/db/models/__init__.py
git -C /Users/angelowashington/CRAVE/backend commit -m "feat(hitlist): add HitlistSave, HitlistSuggestion, HitlistDedupKey models"
```

---

## Task 10: Alembic Migration

**Files:**
- Create: `alembic/versions/<revision>_add_hitlist_tables.py`

- [ ] **Step 1: Generate migration**

```bash
cd /Users/angelowashington/CRAVE/backend
python -m alembic revision --autogenerate -m "add_hitlist_tables"
```

This generates a file like `alembic/versions/xxxx_add_hitlist_tables.py`.

- [ ] **Step 2: Verify the generated file contains all 3 tables**

```bash
cat alembic/versions/*add_hitlist_tables*.py | grep "op.create_table"
```

Expected output contains: `hitlist_saves`, `hitlist_suggestions`, `hitlist_dedup_keys`

If any are missing, check that models are registered in `app/db/models/__init__.py` and retry.

- [ ] **Step 3: Run migration**

```bash
python -m alembic upgrade head
```

Expected: no errors, migration applies cleanly.

- [ ] **Step 4: Verify tables exist**

```bash
python -c "
from app.db.session import SessionLocal
from app.db.models.hitlist_save import HitlistSave
db = SessionLocal()
count = db.query(HitlistSave).count()
print(f'hitlist_saves table ok, rows={count}')
db.close()
"
```

Expected: `hitlist_saves table ok, rows=0`

- [ ] **Step 5: Commit**

```bash
git -C /Users/angelowashington/CRAVE/backend add alembic/versions/
git -C /Users/angelowashington/CRAVE/backend commit -m "feat(hitlist): alembic migration — add hitlist tables"
```

---

## Task 11: Hit List Service Layer

**Files:**
- Create: `app/services/hitlist/__init__.py`
- Create: `app/services/hitlist/spam_guard.py`
- Create: `app/services/hitlist/dedup_engine.py`
- Create: `app/services/hitlist/save_intake.py`
- Create: `app/services/hitlist/suggest_intake.py`
- Create: `app/services/hitlist/get_user_hitlist.py`
- Create: `app/services/hitlist/delete_save.py`
- Create: `app/services/hitlist/aggregator.py`
- Create: `app/services/hitlist/analytics.py`
- Create: `tests/hitlist/test_dedup_engine.py`
- Create: `tests/hitlist/test_aggregator.py`

- [ ] **Step 1: Write dedup engine tests**

```python
# tests/hitlist/test_dedup_engine.py
import pytest
from app.services.hitlist.dedup_engine import compute_dedup_key

def test_place_id_takes_priority():
    key = compute_dedup_key(place_id="abc-123", source_url="https://tiktok.com/x", place_name="Joe's")
    assert key.startswith("place:")
    assert "abc-123" in key

def test_source_url_second():
    key = compute_dedup_key(source_url="https://tiktok.com/@user/video/123", place_name="Joe's")
    assert key.startswith("url:")

def test_geo_third():
    key = compute_dedup_key(place_name="Joe's Tacos", lat=37.7749, lng=-122.4194)
    assert key.startswith("geo:")

def test_city_fourth():
    key = compute_dedup_key(place_name="Joe's Tacos", city="Oakland")
    assert key.startswith("city:")

def test_name_only_fallback():
    key = compute_dedup_key(place_name="Joe's Tacos")
    assert key.startswith("name:")

def test_no_data_raises():
    with pytest.raises(ValueError):
        compute_dedup_key()

def test_same_inputs_produce_same_key():
    k1 = compute_dedup_key(place_name="Joe's Tacos", city="Oakland")
    k2 = compute_dedup_key(place_name="Joe's Tacos", city="Oakland")
    assert k1 == k2

def test_different_names_produce_different_keys():
    k1 = compute_dedup_key(place_name="Joe's Tacos", city="Oakland")
    k2 = compute_dedup_key(place_name="Maria's Tacos", city="Oakland")
    assert k1 != k2

def test_case_insensitive_name():
    k1 = compute_dedup_key(place_name="JOE'S TACOS", city="Oakland")
    k2 = compute_dedup_key(place_name="joe's tacos", city="Oakland")
    assert k1 == k2

def test_geo_rounding():
    # Slight coord difference within 4dp rounds to same key
    k1 = compute_dedup_key(place_name="Test", lat=37.77491, lng=-122.41941)
    k2 = compute_dedup_key(place_name="Test", lat=37.77499, lng=-122.41949)
    assert k1 == k2
```

```python
# tests/hitlist/test_aggregator.py
import pytest
from datetime import datetime, timezone, timedelta
from app.services.hitlist.aggregator import aggregate_saves

def _save(name, city, hours_ago=0):
    return {
        "place_name": name,
        "city": city,
        "timestamp": datetime.now(timezone.utc) - timedelta(hours=hours_ago),
    }

def test_empty_input():
    assert aggregate_saves([]) == []

def test_single_save():
    result = aggregate_saves([_save("Joe's", "Oakland", 0)])
    assert len(result) == 1
    assert result[0]["save_count"] == 1
    assert result[0]["recent_velocity"] == 1

def test_recent_saves_score_higher():
    recent = [_save("Hot Spot", "SF", hours_ago=1)] * 10
    old = [_save("Old Spot", "SF", hours_ago=25)] * 10
    result = aggregate_saves(recent + old)
    scores = {r["place_name"]: r["score"] for r in result}
    assert scores["Hot Spot"] > scores["Old Spot"]

def test_sorted_by_score_descending():
    saves = (
        [_save("Hot", "SF", 1)] * 10 +
        [_save("Medium", "SF", 1)] * 5 +
        [_save("Cold", "SF", 25)] * 10
    )
    result = aggregate_saves(saves)
    scores = [r["score"] for r in result]
    assert scores == sorted(scores, reverse=True)

def test_score_bounded_0_1():
    saves = [_save("Test", "SF", 0)] * 200
    result = aggregate_saves(saves)
    assert 0.0 <= result[0]["score"] <= 1.0
```

- [ ] **Step 2: Run to confirm failure**

```bash
python -m pytest tests/hitlist/ -v 2>&1 | head -10
```

- [ ] **Step 3: Implement all service files**

```python
# app/services/hitlist/__init__.py
```

```python
# app/services/hitlist/spam_guard.py
from __future__ import annotations
import time
from collections import defaultdict, deque
from threading import RLock
from typing import Dict, Deque


class SpamGuard:
    def __init__(self) -> None:
        self._saves: Dict[str, Deque[float]] = defaultdict(deque)
        self._suggests: Dict[str, Deque[float]] = defaultdict(deque)
        self._lock = RLock()

    def allow_save(self, user_id: str, max_per_minute: int = 20) -> bool:
        return self._check(self._saves[user_id], max_per_minute)

    def allow_suggest(self, user_id: str, max_per_minute: int = 10) -> bool:
        return self._check(self._suggests[user_id], max_per_minute)

    def _check(self, window: Deque[float], limit: int) -> bool:
        now = time.time()
        cutoff = now - 60.0
        with self._lock:
            while window and window[0] < cutoff:
                window.popleft()
            if len(window) >= limit:
                return False
            window.append(now)
            return True


spam_guard = SpamGuard()
```

```python
# app/services/hitlist/dedup_engine.py
from __future__ import annotations
import hashlib
from typing import Optional


def _h(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:32]


def _norm(name: str) -> str:
    return " ".join((name or "").lower().strip().split())


def compute_dedup_key(
    *,
    place_id: Optional[str] = None,
    source_url: Optional[str] = None,
    place_name: Optional[str] = None,
    lat: Optional[float] = None,
    lng: Optional[float] = None,
    city: Optional[str] = None,
) -> str:
    if place_id:
        return f"place:{place_id}"
    if source_url:
        return f"url:{_h(source_url.lower().strip())}"
    if place_name and lat is not None and lng is not None:
        return f"geo:{_h(f'{_norm(place_name)}:{round(lat,4)}:{round(lng,4)}')}"
    if place_name and city:
        return f"city:{_h(f'{_norm(place_name)}:{_norm(city)}')}"
    if place_name:
        return f"name:{_h(_norm(place_name))}"
    raise ValueError("Cannot compute dedup key: insufficient data provided")
```

```python
# app/services/hitlist/save_intake.py
from __future__ import annotations
from typing import Optional
from sqlalchemy.orm import Session
from app.db.models.hitlist_save import HitlistSave
from app.db.models.hitlist_dedup_key import HitlistDedupKey
from app.services.social.platform_detect import detect_platform
from app.services.social.url_normalize import normalize_url
from app.services.hitlist.dedup_engine import compute_dedup_key
from app.services.hitlist.spam_guard import spam_guard


def intake_hitlist_save(
    *,
    db: Session,
    user_id: str,
    place_name: str,
    source_url: Optional[str] = None,
    lat: Optional[float] = None,
    lng: Optional[float] = None,
) -> HitlistSave:
    if not spam_guard.allow_save(user_id):
        raise ValueError("Rate limit exceeded")

    norm_url = normalize_url(source_url)
    platform = detect_platform(norm_url) if norm_url else "unknown"

    dedup_key = compute_dedup_key(
        source_url=norm_url,
        place_name=place_name,
        lat=lat,
        lng=lng,
    )

    existing_dedup = (
        db.query(HitlistDedupKey)
        .filter(HitlistDedupKey.user_id == user_id, HitlistDedupKey.dedup_key == dedup_key)
        .one_or_none()
    )
    if existing_dedup:
        existing_save = (
            db.query(HitlistSave)
            .filter(HitlistSave.user_id == user_id, HitlistSave.dedup_key == dedup_key)
            .one_or_none()
        )
        if existing_save:
            return existing_save

    save = HitlistSave(
        user_id=user_id,
        place_name=place_name.strip(),
        source_platform=platform,
        source_url=norm_url,
        lat=lat,
        lng=lng,
        resolution_status="raw",
        dedup_key=dedup_key,
    )
    db.add(save)
    db.add(HitlistDedupKey(user_id=user_id, dedup_key=dedup_key))
    db.flush()
    return save
```

```python
# app/services/hitlist/suggest_intake.py
from __future__ import annotations
from typing import Optional
from sqlalchemy.orm import Session
from app.db.models.hitlist_suggestion import HitlistSuggestion
from app.services.social.platform_detect import detect_platform
from app.services.social.url_normalize import normalize_url
from app.services.hitlist.spam_guard import spam_guard


def intake_suggestion(
    *,
    db: Session,
    user_id: str,
    place_name: str,
    source_url: Optional[str] = None,
    city_hint: Optional[str] = None,
) -> HitlistSuggestion:
    if not spam_guard.allow_suggest(user_id):
        raise ValueError("Rate limit exceeded")

    norm_url = normalize_url(source_url)
    platform = detect_platform(norm_url) if norm_url else "unknown"

    suggestion = HitlistSuggestion(
        user_id=user_id,
        place_name=place_name.strip(),
        city_hint=(city_hint or "").strip() or None,
        source_platform=platform,
        source_url=norm_url,
    )
    db.add(suggestion)
    db.flush()
    return suggestion
```

```python
# app/services/hitlist/get_user_hitlist.py
from __future__ import annotations
from typing import List
from sqlalchemy.orm import Session
from app.db.models.hitlist_save import HitlistSave


def get_user_hitlist(
    *,
    db: Session,
    user_id: str,
    include_resolved: bool = True,
    include_unresolved: bool = True,
    limit: int = 100,
) -> List[HitlistSave]:
    q = db.query(HitlistSave).filter(HitlistSave.user_id == user_id)
    if include_resolved and not include_unresolved:
        q = q.filter(HitlistSave.place_id.isnot(None))
    elif include_unresolved and not include_resolved:
        q = q.filter(HitlistSave.place_id.is_(None))
    return q.order_by(HitlistSave.created_at.desc()).limit(max(1, min(500, limit))).all()
```

```python
# app/services/hitlist/delete_save.py
from __future__ import annotations
from sqlalchemy.orm import Session
from app.db.models.hitlist_save import HitlistSave
from app.db.models.hitlist_dedup_key import HitlistDedupKey


def delete_hitlist_save(*, db: Session, user_id: str, place_name: str) -> bool:
    save = (
        db.query(HitlistSave)
        .filter(HitlistSave.user_id == user_id, HitlistSave.place_name == place_name)
        .first()
    )
    if not save:
        return False
    db.query(HitlistDedupKey).filter(
        HitlistDedupKey.user_id == user_id,
        HitlistDedupKey.dedup_key == save.dedup_key,
    ).delete()
    db.delete(save)
    db.flush()
    return True
```

```python
# app/services/hitlist/aggregator.py
from __future__ import annotations
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Dict, List


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def aggregate_saves(saves: List[dict], window_hours: int = 24) -> List[dict]:
    """
    Input:  [{"place_name": str, "city": str, "timestamp": datetime}, ...]
    Output: [{"place_name", "city", "save_count", "recent_velocity", "score"}, ...]
            sorted by score DESC
    """
    if not saves:
        return []

    cutoff = _utcnow() - timedelta(hours=window_hours)
    grouped: Dict[str, List[dict]] = defaultdict(list)
    for s in saves:
        grouped[f"{s['place_name']}|{s.get('city', '')}"].append(s)

    results = []
    for key, items in grouped.items():
        name, city = key.split("|", 1)
        total = len(items)
        recent = sum(1 for x in items if x["timestamp"] >= cutoff)
        recency_s = recent / max(total, 1)
        volume_s = min(total / 100.0, 1.0)
        score = round(recency_s * 0.70 + volume_s * 0.30, 6)
        results.append({
            "place_name": name,
            "city": city,
            "save_count": total,
            "recent_velocity": recent,
            "score": score,
        })

    return sorted(results, key=lambda x: x["score"], reverse=True)
```

```python
# app/services/hitlist/analytics.py
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Dict
from sqlalchemy.orm import Session
from sqlalchemy import func, select
from app.db.models.hitlist_save import HitlistSave


def get_hitlist_analytics(db: Session) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    saves_today = db.execute(
        select(func.count(HitlistSave.id))
        .where(HitlistSave.created_at >= today_start)
    ).scalar_one()

    unresolved = db.execute(
        select(func.count(HitlistSave.id))
        .where(HitlistSave.place_id.is_(None))
    ).scalar_one()

    promoted = db.execute(
        select(func.count(HitlistSave.id))
        .where(HitlistSave.resolution_status == "promoted")
    ).scalar_one()

    top_rows = db.execute(
        select(HitlistSave.place_name, func.count(HitlistSave.id).label("cnt"))
        .group_by(HitlistSave.place_name)
        .order_by(func.count(HitlistSave.id).desc())
        .limit(10)
    ).all()

    return {
        "saves_today": saves_today,
        "unresolved_count": unresolved,
        "promoted_count": promoted,
        "top_saved_places": [
            {"place_name": r.place_name, "save_count": r.cnt} for r in top_rows
        ],
    }
```

- [ ] **Step 4: Run hitlist service tests**

```bash
python -m pytest tests/hitlist/test_dedup_engine.py tests/hitlist/test_aggregator.py -v
```

Expected: all pass

- [ ] **Step 5: Commit**

```bash
git -C /Users/angelowashington/CRAVE/backend add app/services/hitlist/ tests/hitlist/
git -C /Users/angelowashington/CRAVE/backend commit -m "feat(hitlist): add full hitlist service layer"
```

---

## Task 12: Hit List API Routes

**Files:**
- Create: `app/api/v1/schemas/hitlist.py`
- Create: `app/api/v1/routes/hitlist.py`
- Modify: `app/api/v1/routes/__init__.py`
- Create: `tests/hitlist/test_hitlist_routes.py`

- [ ] **Step 1: Write route tests**

```python
# tests/hitlist/test_hitlist_routes.py
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_save_returns_201():
    resp = client.post("/v1/hitlist/save", json={
        "user_id": "user-test-1",
        "place_name": "Joe's Tacos",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "saved"
    assert "id" in data

def test_save_with_tiktok_url():
    resp = client.post("/v1/hitlist/save", json={
        "user_id": "user-test-2",
        "place_name": "Birria House",
        "source_url": "https://www.tiktok.com/@foodie/video/7123456789",
    })
    assert resp.status_code == 201

def test_save_dedup_returns_same_id():
    payload = {"user_id": "user-dedup-1", "place_name": "Repeat Spot"}
    r1 = client.post("/v1/hitlist/save", json=payload)
    r2 = client.post("/v1/hitlist/save", json=payload)
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["id"] == r2.json()["id"]

def test_get_hitlist():
    user_id = "user-get-1"
    client.post("/v1/hitlist/save", json={"user_id": user_id, "place_name": "Test Place"})
    resp = client.get(f"/v1/hitlist/{user_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert data["total"] >= 1
    item = data["items"][0]
    assert item["place_name"] == "Test Place"
    assert item["resolution_status"] == "raw"

def test_delete_save():
    user_id = "user-del-1"
    client.post("/v1/hitlist/save", json={"user_id": user_id, "place_name": "Delete Me"})
    resp = client.delete(f"/v1/hitlist/delete?user_id={user_id}&place_name=Delete+Me")
    assert resp.status_code == 200
    assert resp.json()["status"] == "deleted"

def test_delete_nonexistent_returns_404():
    resp = client.delete("/v1/hitlist/delete?user_id=nobody&place_name=NoPlace")
    assert resp.status_code == 404

def test_suggest_returns_201():
    resp = client.post("/v1/hitlist/suggest", json={
        "user_id": "user-sug-1",
        "place_name": "New Discovery",
        "city_hint": "Oakland",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert "id" in data
    assert data["place_name"] == "New Discovery"

def test_analytics_endpoint():
    resp = client.get("/v1/hitlist/analytics/summary")
    assert resp.status_code == 200
    data = resp.json()
    for key in ("saves_today", "unresolved_count", "promoted_count", "top_saved_places"):
        assert key in data
```

- [ ] **Step 2: Run to confirm failure**

```bash
python -m pytest tests/hitlist/test_hitlist_routes.py -v 2>&1 | head -10
```

Expected: routes don't exist yet.

- [ ] **Step 3: Create schemas**

```python
# app/api/v1/schemas/hitlist.py
from __future__ import annotations
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class HitlistSaveRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=128)
    place_name: str = Field(..., min_length=1, max_length=256)
    source_url: Optional[str] = Field(None, max_length=1024)
    lat: Optional[float] = Field(None, ge=-90, le=90)
    lng: Optional[float] = Field(None, ge=-180, le=180)


class HitlistSuggestRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=128)
    place_name: str = Field(..., min_length=1, max_length=256)
    source_url: Optional[str] = Field(None, max_length=1024)
    city_hint: Optional[str] = Field(None, max_length=128)


class HitlistItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    place_name: str
    source_platform: Optional[str] = None
    source_url: Optional[str] = None
    place_id: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    resolution_status: str
    created_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None


class HitlistResponse(BaseModel):
    items: List[HitlistItemOut]
    total: int


class HitlistSuggestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    place_name: str
    source_platform: Optional[str] = None
    created_at: Optional[datetime] = None
```

- [ ] **Step 4: Create routes**

```python
# app/api/v1/routes/hitlist.py
from __future__ import annotations
import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.services.hitlist.save_intake import intake_hitlist_save
from app.services.hitlist.suggest_intake import intake_suggestion
from app.services.hitlist.get_user_hitlist import get_user_hitlist
from app.services.hitlist.delete_save import delete_hitlist_save
from app.services.hitlist.analytics import get_hitlist_analytics
from app.api.v1.schemas.hitlist import (
    HitlistSaveRequest, HitlistSuggestRequest,
    HitlistResponse, HitlistItemOut, HitlistSuggestResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/hitlist", tags=["hitlist"])


@router.post("/save", status_code=201)
def save_to_hitlist(payload: HitlistSaveRequest, db: Session = Depends(get_db)):
    try:
        save = intake_hitlist_save(
            db=db,
            user_id=payload.user_id,
            place_name=payload.place_name,
            source_url=payload.source_url,
            lat=payload.lat,
            lng=payload.lng,
        )
        db.commit()
        return {"status": "saved", "id": save.id, "dedup_key": save.dedup_key}
    except ValueError as exc:
        raise HTTPException(
            status_code=429 if "Rate limit" in str(exc) else 400,
            detail=str(exc),
        )
    except Exception as exc:
        db.rollback()
        logger.exception("hitlist_save_failed user=%s error=%s", payload.user_id, exc)
        raise HTTPException(status_code=500, detail="Save failed")


@router.get("/analytics/summary")
def hitlist_analytics(db: Session = Depends(get_db)):
    return get_hitlist_analytics(db)


@router.get("/{user_id}", response_model=HitlistResponse)
def get_hitlist(
    user_id: str,
    include_resolved: bool = Query(True),
    include_unresolved: bool = Query(True),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    items = get_user_hitlist(
        db=db,
        user_id=user_id,
        include_resolved=include_resolved,
        include_unresolved=include_unresolved,
        limit=limit,
    )
    return HitlistResponse(
        items=[HitlistItemOut.model_validate(i) for i in items],
        total=len(items),
    )


@router.delete("/delete")
def delete_save(
    user_id: str = Query(...),
    place_name: str = Query(...),
    db: Session = Depends(get_db),
):
    deleted = delete_hitlist_save(db=db, user_id=user_id, place_name=place_name)
    if not deleted:
        raise HTTPException(status_code=404, detail="Save not found")
    db.commit()
    return {"status": "deleted"}


@router.post("/suggest", response_model=HitlistSuggestResponse, status_code=201)
def suggest_place(payload: HitlistSuggestRequest, db: Session = Depends(get_db)):
    try:
        suggestion = intake_suggestion(
            db=db,
            user_id=payload.user_id,
            place_name=payload.place_name,
            source_url=payload.source_url,
            city_hint=payload.city_hint,
        )
        db.commit()
        return HitlistSuggestResponse.model_validate(suggestion)
    except ValueError as exc:
        raise HTTPException(
            status_code=429 if "Rate limit" in str(exc) else 400,
            detail=str(exc),
        )
    except Exception as exc:
        db.rollback()
        logger.exception("hitlist_suggest_failed user=%s error=%s", payload.user_id, exc)
        raise HTTPException(status_code=500, detail="Suggestion failed")
```

- [ ] **Step 5: Register router in `app/api/v1/routes/__init__.py`**

Add at the end of the existing imports:

```python
from app.api.v1.routes.hitlist import router as hitlist_router
```

Add at the end of the router inclusions:

```python
router.include_router(hitlist_router)
```

- [ ] **Step 6: Run all hitlist tests**

```bash
python -m pytest tests/hitlist/ -v
```

Expected: all pass

- [ ] **Step 7: Verify server starts cleanly**

```bash
python -c "from app.main import app; print('app ok')"
```

- [ ] **Step 8: Commit**

```bash
git -C /Users/angelowashington/CRAVE/backend add app/api/v1/schemas/hitlist.py app/api/v1/routes/hitlist.py app/api/v1/routes/__init__.py tests/hitlist/
git -C /Users/angelowashington/CRAVE/backend commit -m "feat(hitlist): add Crave's Hit List — save/suggest/get/delete + analytics routes"
```

---

## Task 13: Full Test Run + Recompute Validation

- [ ] **Step 1: Run complete test suite**

```bash
cd /Users/angelowashington/CRAVE/backend
python -m pytest tests/ -v --tb=short 2>&1 | tail -30
```

Expected: all tests pass, no regressions.

- [ ] **Step 2: Enqueue and run recompute to validate scoring**

```bash
# Ensure queue dir exists
mkdir -p /Users/angelowashington/CRAVE/backend/var/queue

# Enqueue a recompute job
python -c "
import json
from pathlib import Path
from datetime import datetime, timezone

queue = Path('/Users/angelowashington/CRAVE/backend/var/queue/recompute_scores.queue')
queue.write_text(json.dumps({
    'type': 'recompute_scores',
    'created_at': datetime.now(timezone.utc).isoformat(),
    'payload': {'limit': 100},
}) + '\n')
print('job enqueued')
"

# Run the worker
python -c "
from app.workers.recompute_scores_worker import run_worker_once
updated = run_worker_once()
print(f'scored {updated} places')
"
```

Expected: `scored N places` where N > 0.

- [ ] **Step 3: Verify score distribution improved**

```bash
python -c "
from app.db.session import SessionLocal
from app.db.models.place import Place
from sqlalchemy import func

db = SessionLocal()
try:
    rows = db.execute(
        __import__('sqlalchemy').text(
            'SELECT MIN(rank_score), MAX(rank_score), AVG(rank_score), '
            'COUNT(CASE WHEN rank_score > 0.3 THEN 1 END) as rich, '
            'COUNT(*) as total FROM places WHERE is_active = 1'
        )
    ).fetchone()
    print(f'min={rows[0]:.4f} max={rows[1]:.4f} avg={rows[2]:.4f} '
          f'rich(>0.3)={rows[3]} total={rows[4]}')
finally:
    db.close()
"
```

Expected: `avg` is meaningfully above `0.02`. `rich` count > 0.

- [ ] **Step 4: Final commit**

```bash
git -C /Users/angelowashington/CRAVE/backend add .
git -C /Users/angelowashington/CRAVE/backend commit -m "chore: production finalization complete — scoring v3, mapbox geojson, social layer, crave hit list"
```

---

## Self-Review Against Spec

**Spec coverage check:**

| Spec Requirement | Task |
|---|---|
| Multi-source 9-signal scoring | Tasks 1–4 |
| City-aware weight profiles | Task 2 |
| Missing data re-normalization | Task 3 (`_redistribute_weights`) |
| Batch queries, no N+1 | Task 4 (`_fetch_signal_context`) |
| `/map/geojson` with percentile tiers | Tasks 5–6 |
| Existing `/map` untouched | Task 6 (additive only) |
| Social: platform_detect | Task 7 |
| Social: url_normalize | Task 7 |
| Social: caption_parser | Task 8 |
| Social: TikTok/IG/YouTube extractors | Task 8 |
| Social layer non-authoritative | All social tasks — no truth writes |
| HitlistSave model + dedup | Tasks 9–11 |
| HitlistSuggestion model | Task 9 |
| HitlistDedupKey model | Task 9 |
| Alembic migration | Task 10 |
| Dedup priority chain (4 levels) | Task 11 |
| resolution_status enum | Task 9 model + Task 12 schema |
| source_platform on intake | Task 11 (save_intake + suggest_intake) |
| Rate limit save (20/min) | Task 11 (spam_guard) |
| Rate limit suggest (10/min) | Task 11 (spam_guard) |
| Velocity scoring 70/30 | Task 11 (aggregator) |
| Analytics endpoint | Tasks 11–12 |
| 4 hitlist API routes | Task 12 |
| No regressions | Task 13 full test run |
| Score distribution validated | Task 13 |
