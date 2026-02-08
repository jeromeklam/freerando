#!/usr/bin/env python3
"""Backfill CLIP embeddings for already-analyzed photos that don't have them yet."""

import os
import sys
import time
import numpy as np
import psycopg2
import config

# Re-use model loading from analyze_photos
from analyze_photos import load_image, get_clip, embedding_to_bytes


def get_db():
    return psycopg2.connect(
        host=config.PG_HOST,
        port=config.PG_PORT,
        dbname=config.PG_DATABASE,
        user=config.PG_USER,
        password=config.PG_PASSWORD,
    )


def compute_embedding(img_pil):
    """Compute CLIP embedding for an image (without tag matching)."""
    import torch

    model, preprocess, _ = get_clip()
    image = preprocess(img_pil).unsqueeze(0)

    with torch.no_grad():
        features = model.encode_image(image)
        features /= features.norm(dim=-1, keepdim=True)

    return features.squeeze(0).cpu().numpy().astype(np.float32)


def main():
    conn = get_db()
    cur = conn.cursor()

    # Count photos needing backfill
    cur.execute("""
        SELECT COUNT(*) FROM photos
        WHERE clip_analyzed = TRUE AND clip_embedding IS NULL
        AND extension IN ('.HEIC', '.JPG', '.JPEG', '.PNG')
    """)
    total = cur.fetchone()[0]
    print(f"=== CLIP Embedding Backfill ===")
    print(f"  Photos to process: {total}")

    if total == 0:
        print("  Nothing to do.")
        cur.close()
        conn.close()
        return

    batch_size = 20
    processed = 0
    errors = 0
    start = time.time()

    while True:
        cur.execute("""
            SELECT id, filepath FROM photos
            WHERE clip_analyzed = TRUE AND clip_embedding IS NULL
            AND extension IN ('.HEIC', '.JPG', '.JPEG', '.PNG')
            ORDER BY id LIMIT %s
        """, (batch_size,))
        rows = cur.fetchall()

        if not rows:
            break

        for photo_id, relpath in rows:
            fullpath = os.path.join(config.PHOTOS_ROOT, relpath)
            if not os.path.exists(fullpath):
                # Mark as done (no embedding possible)
                cur.execute(
                    "UPDATE photos SET clip_embedding = %s WHERE id = %s",
                    (psycopg2.Binary(b''), photo_id),
                )
                continue

            try:
                img_pil, _ = load_image(fullpath)
                embedding = compute_embedding(img_pil)
                emb_bytes = embedding_to_bytes(embedding)

                cur.execute(
                    "UPDATE photos SET clip_embedding = %s WHERE id = %s",
                    (psycopg2.Binary(emb_bytes), photo_id),
                )
                processed += 1
            except Exception as e:
                print(f"\n  Error {relpath}: {e}", file=sys.stderr)
                cur.execute(
                    "UPDATE photos SET clip_embedding = %s WHERE id = %s",
                    (psycopg2.Binary(b''), photo_id),
                )
                errors += 1

        conn.commit()

        elapsed = time.time() - start
        rate = processed / elapsed if elapsed > 0 else 0
        print(
            f"  {processed}/{total} ({rate:.1f}/s) errors={errors}   ",
            end="\r",
        )

    elapsed = time.time() - start
    print(f"\n\nDone in {elapsed:.0f}s")
    print(f"  Processed: {processed}")
    print(f"  Errors: {errors}")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
