"""
Image safety + sanity checks for the disease scanner.

* load_and_normalize()  - validates the upload and returns a clean RGB image
                          (fixes phone rotation, transparency, huge photos).
* plant_pixel_ratio()   - how much of the picture has leaf-like colours.
* sharpness_score()     - rough focus measure (low = blurry).
"""
import os

import numpy as np
from PIL import Image, ImageOps

MAX_UPLOAD_BYTES = 10 * 1024 * 1024      # 10 MB
MIN_SIDE_PIXELS = 96                     # smaller than this is useless
MAX_SIDE_PIXELS = 1600                   # larger photos are scaled down


class ImageCheckError(ValueError):
    """Raised with a user-friendly message when an upload can't be used."""


def load_and_normalize(file_storage):
    """Validate a Flask FileStorage and return a clean RGB PIL image."""

    stream = file_storage.stream

    stream.seek(0, os.SEEK_END)
    size = stream.tell()
    stream.seek(0)

    if size == 0:
        raise ImageCheckError("The uploaded file is empty.")

    if size > MAX_UPLOAD_BYTES:
        raise ImageCheckError(
            f"The image is too large ({size / 1024 / 1024:.1f} MB). "
            f"Please upload a photo under {MAX_UPLOAD_BYTES // 1024 // 1024} MB."
        )

    try:
        img = Image.open(stream)
        img.load()
    except Exception:
        raise ImageCheckError(
            "This file could not be read as an image. Please upload a JPG, PNG "
            "or WebP photo (iPhone HEIC photos must be exported as JPG first)."
        )

    # Phones store rotation in EXIF; apply it so the leaf is upright.
    img = ImageOps.exif_transpose(img)

    # Flatten transparency onto white, then force RGB.
    if img.mode in ("RGBA", "LA") or (
        img.mode == "P" and "transparency" in img.info
    ):
        rgba = img.convert("RGBA")
        background = Image.new("RGB", rgba.size, (255, 255, 255))
        background.paste(rgba, mask=rgba.split()[-1])
        img = background
    else:
        img = img.convert("RGB")

    width, height = img.size

    if min(width, height) < MIN_SIDE_PIXELS:
        raise ImageCheckError(
            f"The image is too small ({width}x{height}px). "
            f"Please use a photo at least {MIN_SIDE_PIXELS}px on each side."
        )

    if max(width, height) > MAX_SIDE_PIXELS:
        img.thumbnail((MAX_SIDE_PIXELS, MAX_SIDE_PIXELS))

    return img


def save_as_jpeg(img, path):
    """Save the cleaned image (also strips metadata such as GPS)."""
    img.save(path, "JPEG", quality=92)


def plant_pixel_ratio(img):
    """
    Fraction (0-1) of pixels that have green / yellow / brown leaf colours.
    A photo of a face, a wall or a screenshot scores close to 0.
    """
    small = img.copy()
    small.thumbnail((192, 192))

    hsv = np.asarray(small.convert("HSV"), dtype=np.int32)
    hue, sat, val = hsv[..., 0], hsv[..., 1], hsv[..., 2]

    # PIL hue runs 0-255 for 0-360 degrees: 14-120 is roughly 20-170 degrees.
    mask = (hue >= 14) & (hue <= 120) & (sat >= 35) & (val >= 40)
    return float(mask.mean())


def sharpness_score(img):
    """Variance of the Laplacian on a 256px copy. Low values mean blurry."""
    gray = np.asarray(
        img.convert("L").resize((256, 256)), dtype=np.float32
    )
    laplacian = (
        -4.0 * gray[1:-1, 1:-1]
        + gray[:-2, 1:-1]
        + gray[2:, 1:-1]
        + gray[1:-1, :-2]
        + gray[1:-1, 2:]
    )
    return float(laplacian.var())