"""Generate and serve photo thumbnails with disk caching."""

import os
import pillow_heif
pillow_heif.register_heif_opener()
from PIL import Image
import config


def get_thumbnail_path(photo_id, size=300):
    """Return path to cached thumbnail, or None if not cached yet."""
    path = os.path.join(config.THUMBNAIL_DIR, str(size), f"{photo_id}.jpg")
    if os.path.exists(path):
        return path
    return None


def generate_thumbnail(filepath, photo_id, size=300):
    """Generate a thumbnail and cache it to disk. Returns the path."""
    fullpath = os.path.join(config.PHOTOS_ROOT, filepath)
    if not os.path.exists(fullpath):
        return None

    cache_path = os.path.join(config.THUMBNAIL_DIR, str(size), f"{photo_id}.jpg")

    # Check cache
    if os.path.exists(cache_path):
        return cache_path

    try:
        img = Image.open(fullpath).convert("RGB")

        # Resize maintaining aspect ratio
        img.thumbnail((size, size), Image.LANCZOS)

        # Save as JPEG
        img.save(cache_path, "JPEG", quality=80, optimize=True)
        return cache_path
    except Exception as e:
        print(f"Thumbnail error {filepath}: {e}")
        return None


def get_face_crop_path(face_id):
    """Return path to any cached face crop for this face_id, or None."""
    faces_dir = os.path.join(config.THUMBNAIL_DIR, "faces")
    # Face crops are named {face_id}_{photo_id}.jpg
    for fname in os.listdir(faces_dir):
        if fname.startswith(f"{face_id}_") and fname.endswith(".jpg"):
            return os.path.join(faces_dir, fname)
    return None


def generate_face_crop(photo_filepath, face_id, photo_id, bbox, size=150):
    """Generate a face crop thumbnail. bbox = [x1, y1, x2, y2]."""
    cache_path = os.path.join(config.THUMBNAIL_DIR, "faces", f"{face_id}_{photo_id}.jpg")
    if os.path.exists(cache_path):
        return cache_path

    fullpath = os.path.join(config.PHOTOS_ROOT, photo_filepath)
    if not os.path.exists(fullpath):
        return None

    try:
        img = Image.open(fullpath).convert("RGB")

        # Add padding around face bbox
        x1, y1, x2, y2 = bbox
        w = x2 - x1
        h = y2 - y1
        pad = int(max(w, h) * 0.3)
        x1 = max(0, x1 - pad)
        y1 = max(0, y1 - pad)
        x2 = min(img.width, x2 + pad)
        y2 = min(img.height, y2 + pad)

        crop = img.crop((x1, y1, x2, y2))
        crop.thumbnail((size, size), Image.LANCZOS)
        crop.save(cache_path, "JPEG", quality=85)
        return cache_path
    except Exception as e:
        print(f"Face crop error: {e}")
        return None
