from __future__ import annotations

from PIL import Image
import imagehash


def generate_phash(image: Image.Image) -> str:
    """
    Generate perceptual hash from image.

    Must be called on PROCESSED image, not original.
    """
    try:
        phash = imagehash.phash(image)
        return str(phash)
    except Exception:
        return ""


def compare_phashes(hash1: str, hash2: str) -> int:
    """
    Return distance between two hashes.
    Lower = more similar.
    """
    try:
        h1 = imagehash.hex_to_hash(hash1)
        h2 = imagehash.hex_to_hash(hash2)
        return h1 - h2
    except Exception:
        return 999