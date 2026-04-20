from __future__ import annotations

from typing import Tuple

from PIL import Image, ImageFilter, ImageEnhance, ImageOps

from app.utils.exif import auto_orient, strip_exif


# Optional OpenCV (denoise)
try:
    import cv2
    import numpy as np
    OPENCV_AVAILABLE = True
except Exception:
    OPENCV_AVAILABLE = False


MAX_SIZE = 1280
THUMB_SIZE = 400


# -------------------------
# Resize
# -------------------------

def resize_image(image: Image.Image, max_size: int = MAX_SIZE) -> Image.Image:
    image.thumbnail((max_size, max_size), Image.LANCZOS)
    return image


# -------------------------
# Denoise (optional)
# -------------------------

def denoise_image(image: Image.Image) -> Image.Image:
    if not OPENCV_AVAILABLE:
        return image

    try:
        img = np.array(image)
        img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

        denoised = cv2.fastNlMeansDenoisingColored(
            img,
            None,
            5,   # strength
            5,
            7,
            21
        )

        denoised = cv2.cvtColor(denoised, cv2.COLOR_BGR2RGB)
        return Image.fromarray(denoised)
    except Exception:
        return image


# -------------------------
# Sharpen
# -------------------------

def sharpen_image(image: Image.Image) -> Image.Image:
    try:
        return image.filter(
            ImageFilter.UnsharpMask(radius=1, percent=120, threshold=3)
        )
    except Exception:
        return image


# -------------------------
# Contrast
# -------------------------

def apply_autocontrast(image: Image.Image) -> Image.Image:
    try:
        return ImageOps.autocontrast(image, cutoff=0.5)
    except Exception:
        return image


# -------------------------
# Saturation
# -------------------------

def boost_saturation(image: Image.Image) -> Image.Image:
    try:
        enhancer = ImageEnhance.Color(image)
        return enhancer.enhance(1.1)
    except Exception:
        return image


# -------------------------
# Save JPEG
# -------------------------

def save_jpeg(image: Image.Image) -> bytes:
    from io import BytesIO

    buffer = BytesIO()

    image = image.convert("RGB")

    image.save(
        buffer,
        format="JPEG",
        quality=78,
        optimize=True,
    )

    return buffer.getvalue()


# -------------------------
# Full Processing Pipeline
# -------------------------

def process_image(image: Image.Image) -> Image.Image:
    """
    Full pipeline (ORDER IS CRITICAL)
    """

    image = auto_orient(image)
    image = resize_image(image)
    image = denoise_image(image)
    image = sharpen_image(image)
    image = apply_autocontrast(image)
    image = boost_saturation(image)
    image = strip_exif(image)

    return image


# -------------------------
# Thumbnail Pipeline
# -------------------------

def process_thumbnail(image: Image.Image) -> Image.Image:
    """
    Lightweight version for thumbnails
    (skip denoise)
    """

    image = auto_orient(image)
    image.thumbnail((THUMB_SIZE, THUMB_SIZE), Image.LANCZOS)
    image = apply_autocontrast(image)
    image = boost_saturation(image)
    image = strip_exif(image)

    return image