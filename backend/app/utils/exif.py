from __future__ import annotations

from PIL import Image, ImageOps


def auto_orient(image: Image.Image) -> Image.Image:
    """
    Fix image orientation using EXIF data.
    Must be run BEFORE any processing.
    """
    try:
        return ImageOps.exif_transpose(image)
    except Exception:
        return image


def strip_exif(image: Image.Image) -> Image.Image:
    """
    Remove EXIF metadata (GPS, device info, etc.)
    Ensures privacy + smaller file size.
    """
    try:
        data = list(image.getdata())
        clean = Image.new(image.mode, image.size)
        clean.putdata(data)
        return clean
    except Exception:
        return image