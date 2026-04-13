from app.db.session import SessionLocal
from app.db.models.discovery_candidate import DiscoveryCandidate
from app.db.models.place import Place


CONFIDENCE_THRESHOLD = 0.72


def run():
    db = SessionLocal()

    try:
        # ----------------------------------------
        # Find Eligible Candidates
        # ----------------------------------------
        candidates = (
            db.query(DiscoveryCandidate)
            .filter(DiscoveryCandidate.status == "candidate")
            .filter(DiscoveryCandidate.resolved.is_(False))
            .filter(DiscoveryCandidate.blocked.is_(False))
            .filter(DiscoveryCandidate.confidence_score >= CONFIDENCE_THRESHOLD)
            .all()
        )

        promoted_count = 0

        for candidate in candidates:
            # Prevent duplicate promotion
            existing = (
                db.query(Place)
                .filter(Place.name == candidate.name)
                .filter(Place.city_id == candidate.city_id)
                .first()
            )

            if existing:
                candidate.resolved = True
                continue

            # Create new Place
            place = Place(
                name=candidate.name,
                city_id=candidate.city_id,
            )

            db.add(place)

            # Mark candidate resolved
            candidate.resolved = True

            promoted_count += 1

        db.commit()

        print(f"Eligible candidates found: {len(candidates)}")
        print(f"Promoted: {promoted_count}")

    except Exception as e:
        db.rollback()
        print("ERROR during promotion:", e)
        raise

    finally:
        db.close()


if __name__ == "__main__":
    run()