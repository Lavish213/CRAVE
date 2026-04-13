from __future__ import annotations

from app.db.session import SessionLocal
from app.services.discovery.pipeline_v2 import run_discovery_pipeline_v2


def main() -> None:
    db = SessionLocal()

    try:
        result = run_discovery_pipeline_v2(
            db=db,
            limit=50,
        )

        print("=== DISCOVERY V2 PIPELINE ===")
        for k, v in result.items():
            print(f"{k}: {v}")

    except Exception as e:
        db.rollback()
        print("Pipeline failed:", type(e).__name__, str(e))
        raise

    finally:
        db.close()


if __name__ == "__main__":
    main()