from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.menu.extraction.replay_corpus import run_replay_manifest  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Replay deterministic menu fixtures")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--json", action="store_true", dest="json_output")
    args = parser.parse_args()

    report = run_replay_manifest(args.manifest)
    if args.json_output:
        print(json.dumps(report, sort_keys=True))
    else:
        for case in report["cases"]:
            print(
                f"{case['status'].upper()} {case['id']}: "
                f"items={case['item_count']} price_coverage={case['price_coverage']}"
            )
        print(
            f"total={report['total']} passed={report['passed']} failed={report['failed']}"
        )

    return 0 if report["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
