# backend/ingest/build_seed.py

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ingest.normalize import normalize


# =========================================================
# PATHS (LOCKED, CWD-INDEPENDENT)
# =========================================================
BACKEND_DIR = Path(__file__).resolve().parents[1]
RAW_DIR = BACKEND_DIR / "data" / "raw"
PROCESSED_DIR = BACKEND_DIR / "data" / "processed"


# =========================================================
# HELPERS
# =========================================================
def _load_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"❌ Invalid JSON in {path}: {e}") from e
    except Exception as e:
        raise RuntimeError(f"❌ Failed to read {path}: {e}") from e


def _write_json(path: Path, payload: dict) -> None:
    try:
        path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception as e:
        raise RuntimeError(f"❌ Failed to write {path}: {e}") from e


# =========================================================
# MAIN
# =========================================================
def main() -> None:
    input_files = sorted(RAW_DIR.glob("*_places.json"))

    if not input_files:
        raise RuntimeError(
            "❌ No *_places.json files found in backend/data/raw"
        )

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    for raw_file in input_files:
        city_slug = raw_file.stem.replace("_places", "")

        print(f"🔄 Processing city: {city_slug}")

        raw_payload = _load_json(raw_file)

        if not raw_payload:
            print(f"⚠️  Skipping {city_slug}: empty raw input")
            continue

        if not isinstance(raw_payload, dict):
            print(f"⚠️  Skipping {city_slug}: expected OSM dict payload")
            continue

        places = normalize(raw_payload)

        if not places:
            print(f"⚠️  Skipping {city_slug}: nothing valid after normalize")
            continue

        seed = {
            "city": city_slug,
            "version": "v1",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "places": places,
        }

        out_file = PROCESSED_DIR / f"{city_slug}_v1.json"
        _write_json(out_file, seed)

        print(f"✅ Built seed: {out_file} ({len(places)} places)")

    print("🎉 Seed build complete.")


if __name__ == "__main__":
    main()