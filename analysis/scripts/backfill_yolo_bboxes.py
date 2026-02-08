#!/usr/bin/env python3
"""Backfill YOLO bounding boxes for already-analyzed photos that don't have them."""

import os
import sys
import time
import psycopg2
import config


def get_db():
    return psycopg2.connect(
        host=config.PG_HOST,
        port=config.PG_PORT,
        dbname=config.PG_DATABASE,
        user=config.PG_USER,
        password=config.PG_PASSWORD,
    )


def main():
    conn = get_db()
    cur = conn.cursor()

    # Find photos that have YOLO tags but no bboxes
    cur.execute("""
        SELECT DISTINCT p.id, p.filepath
        FROM photos p
        JOIN photo_tags pt ON pt.photo_id = p.id
        WHERE pt.source = 'yolo' AND pt.bbox_x1 IS NULL
        AND p.extension IN ('.HEIC', '.JPG', '.JPEG', '.PNG')
        ORDER BY p.id
    """)
    rows = cur.fetchall()
    total = len(rows)
    print(f"=== YOLO BBox Backfill ===")
    print(f"  Photos to re-analyze: {total}")

    if total == 0:
        print("  Nothing to do.")
        cur.close()
        conn.close()
        return

    from analyze_photos import analyze_yolo

    processed = 0
    errors = 0
    start = time.time()

    for photo_id, relpath in rows:
        fullpath = os.path.join(config.PHOTOS_ROOT, relpath)
        if not os.path.exists(fullpath):
            processed += 1
            continue

        try:
            detections = analyze_yolo(fullpath)
            for label, conf, bbox in detections:
                tag_fr = config.translate_tag(label)
                cur.execute("""
                    UPDATE photo_tags
                    SET bbox_x1 = %s, bbox_y1 = %s, bbox_x2 = %s, bbox_y2 = %s
                    WHERE photo_id = %s AND tag = %s AND source = 'yolo'
                """, (bbox[0], bbox[1], bbox[2], bbox[3], photo_id, tag_fr))
            processed += 1
        except Exception as e:
            print(f"\n  Error {relpath}: {e}", file=sys.stderr)
            errors += 1

        if processed % 20 == 0:
            conn.commit()
            elapsed = time.time() - start
            rate = processed / elapsed if elapsed > 0 else 0
            print(
                f"  {processed}/{total} ({rate:.1f}/s) errors={errors}   ",
                end="\r",
            )

    conn.commit()
    elapsed = time.time() - start
    print(f"\n\nDone in {elapsed:.0f}s")
    print(f"  Processed: {processed}, Errors: {errors}")
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
