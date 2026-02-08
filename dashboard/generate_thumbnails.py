#!/usr/bin/env python3
"""Batch pre-generate thumbnails for all photos and face crops."""

import sys
import time
import psycopg2
import config
from services.thumbnail_service import (
    get_thumbnail_path, generate_thumbnail,
    get_face_crop_path, generate_face_crop,
)


def get_db():
    return psycopg2.connect(
        host=config.PG_HOST, port=config.PG_PORT,
        dbname=config.PG_DATABASE, user=config.PG_USER,
        password=config.PG_PASSWORD,
    )


def generate_photo_thumbnails(size=300):
    """Generate thumbnails for all photos that don't have one yet."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, filepath FROM photos ORDER BY id")
    rows = cur.fetchall()
    cur.close()
    conn.close()

    total = len(rows)
    generated = 0
    skipped = 0
    errors = 0

    print(f"[Thumbnails {size}px] {total} photos to check...")

    for i, (photo_id, filepath) in enumerate(rows, 1):
        if get_thumbnail_path(photo_id, size):
            skipped += 1
            continue

        path = generate_thumbnail(filepath, photo_id, size)
        if path:
            generated += 1
        else:
            errors += 1

        if i % 100 == 0:
            print(f"  [{i}/{total}] generated={generated} skipped={skipped} errors={errors}")

    print(f"[Thumbnails {size}px] Done: generated={generated} skipped={skipped} errors={errors}")
    return generated


def generate_face_crops():
    """Generate face crops for all faces that don't have one yet."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT DISTINCT ON (pf.face_id)
               pf.face_id, pf.photo_id, p.filepath,
               pf.bbox_x1, pf.bbox_y1, pf.bbox_x2, pf.bbox_y2
        FROM photo_faces pf
        JOIN photos p ON p.id = pf.photo_id
        ORDER BY pf.face_id, pf.id
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()

    total = len(rows)
    generated = 0
    skipped = 0
    errors = 0

    print(f"[Face crops] {total} faces to check...")

    for i, (face_id, photo_id, filepath, x1, y1, x2, y2) in enumerate(rows, 1):
        if get_face_crop_path(face_id):
            skipped += 1
            continue

        path = generate_face_crop(filepath, face_id, photo_id, [x1, y1, x2, y2])
        if path:
            generated += 1
        else:
            errors += 1

        if i % 50 == 0:
            print(f"  [{i}/{total}] generated={generated} skipped={skipped} errors={errors}")

    print(f"[Face crops] Done: generated={generated} skipped={skipped} errors={errors}")
    return generated


if __name__ == "__main__":
    start = time.time()

    # 300px thumbnails (grid)
    generate_photo_thumbnails(300)

    # 1200px thumbnails (lightbox) — optional, can be slow
    if "--full" in sys.argv:
        generate_photo_thumbnails(1200)

    # Face crops
    generate_face_crops()

    elapsed = time.time() - start
    print(f"\nTotal time: {elapsed:.1f}s")
