import os
import requests

from app.db.session import SessionLocal
from app.db.models.place import Place
from app.db.models.place_image import PlaceImage

GOOGLE_API_KEY = os.getenv("AIzaSyBocXFlmggr_Qv6djHTnt2uRKHKpppWjug")


def get_google_image(place):
    try:
        url = "https://maps.googleapis.com/maps/api/place/findplacefromtext/json"

        params = {
            "input": place.name,
            "inputtype": "textquery",
            "fields": "place_id,photos",
            "locationbias": f"circle:2000@{place.lat},{place.lng}",
            "key": GOOGLE_API_KEY,
        }

        r = requests.get(url, params=params, timeout=10).json()

        candidates = r.get("candidates", [])
        if not candidates:
            return None

        photos = candidates[0].get("photos")
        if not photos:
            return None

        ref = photos[0]["photo_reference"]

        image_url = (
            "https://maps.googleapis.com/maps/api/place/photo"
            f"?maxwidth=800&photo_reference={ref}&key={GOOGLE_API_KEY}"
        )

        return image_url

    except Exception:
        return None


def run():
    db = SessionLocal()

    places = db.query(Place).all()

    created = 0
    skipped = 0

    for p in places:
        existing = db.query(PlaceImage).filter(
            PlaceImage.place_id == p.id,
            PlaceImage.is_primary == True
        ).first()

        if existing:
            skipped += 1
            continue

        image = get_google_image(p)

        if not image:
            continue

        row = PlaceImage(
            place_id=p.id,
            url=image,
            source="google",
            is_primary=True,
        )

        db.add(row)
        db.commit()

        created += 1

        print("ADDED", p.name)

    print("DONE")
    print("CREATED:", created)
    print("SKIPPED:", skipped)


if __name__ == "__main__":
    run()