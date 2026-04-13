from __future__ import annotations

import argparse
import json

from app.db.session import SessionLocal
from app.workers.menu_crawler_worker import crawl_menu_batch


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=25)
    parser.add_argument("--sleep-seconds", type=float, default=0.0)
    parser.add_argument("--max-errors", type=int, default=10)
    parser.add_argument("--place-id", action="append", dest="place_ids", default=None)
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    db = SessionLocal()

    try:
        result = crawl_menu_batch(
            db=db,
            limit=args.limit,
            sleep_seconds=args.sleep_seconds,
            max_errors=args.max_errors,
            place_ids=args.place_ids,
        )
        print(json.dumps(result, indent=2, default=str))
    finally:
        db.close()


if __name__ == "__main__":
    main()