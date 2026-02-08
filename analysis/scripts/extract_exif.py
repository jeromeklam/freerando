#!/usr/bin/env python3
"""Extract EXIF metadata from photos and store in PostgreSQL."""

import os
import sys
import time
import subprocess
import json
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


def scan_photos(conn):
    """Insert new photos into the database."""
    cur = conn.cursor()
    count = 0
    for dirpath, _dirs, files in os.walk(config.PHOTOS_ROOT):
        for fname in files:
            ext = os.path.splitext(fname)[1].upper()
            if ext not in (".HEIC", ".JPG", ".JPEG", ".PNG", ".MOV", ".MP4", ".GIF"):
                continue
            filepath = os.path.join(dirpath, fname)
            relpath = os.path.relpath(filepath, config.PHOTOS_ROOT)

            try:
                stat = os.stat(filepath)
            except OSError:
                continue

            cur.execute(
                """INSERT INTO photos (filepath, filename, extension, filesize, file_modified)
                   VALUES (%s, %s, %s, %s, to_timestamp(%s))
                   ON CONFLICT (filepath) DO NOTHING""",
                (relpath, fname, ext, stat.st_size, stat.st_mtime),
            )
            if cur.rowcount > 0:
                count += 1

    conn.commit()
    cur.close()
    return count


def extract_exif_batch(conn, batch_size=100):
    """Extract EXIF from photos not yet processed."""
    cur = conn.cursor()
    cur.execute(
        """SELECT id, filepath FROM photos
           WHERE exif_extracted = FALSE
           AND extension IN ('.HEIC', '.JPG', '.JPEG', '.PNG')
           ORDER BY id
           LIMIT %s""",
        (batch_size,),
    )
    rows = cur.fetchall()

    if not rows:
        return 0

    processed = 0
    for photo_id, relpath in rows:
        fullpath = os.path.join(config.PHOTOS_ROOT, relpath)
        if not os.path.exists(fullpath):
            cur.execute(
                "UPDATE photos SET exif_extracted = TRUE WHERE id = %s",
                (photo_id,),
            )
            continue

        exif = read_exif(fullpath)
        if exif:
            lat = exif.get("latitude")
            lon = exif.get("longitude")
            location_sql = None
            if lat is not None and lon is not None:
                location_sql = f"SRID=4326;POINT({lon} {lat})"

            cur.execute(
                """UPDATE photos SET
                    date_taken = %s,
                    camera_make = %s,
                    camera_model = %s,
                    lens_model = %s,
                    focal_length = %s,
                    aperture = %s,
                    shutter_speed = %s,
                    iso = %s,
                    width = %s,
                    height = %s,
                    latitude = %s,
                    longitude = %s,
                    altitude = %s,
                    gps_accuracy = %s,
                    location = %s,
                    exif_extracted = TRUE,
                    updated_at = NOW()
                WHERE id = %s""",
                (
                    exif.get("date_taken"),
                    exif.get("camera_make"),
                    exif.get("camera_model"),
                    exif.get("lens_model"),
                    exif.get("focal_length"),
                    exif.get("aperture"),
                    exif.get("shutter_speed"),
                    exif.get("iso"),
                    exif.get("width"),
                    exif.get("height"),
                    lat,
                    lon,
                    exif.get("altitude"),
                    exif.get("gps_accuracy"),
                    location_sql,
                    photo_id,
                ),
            )
        else:
            cur.execute(
                "UPDATE photos SET exif_extracted = TRUE, updated_at = NOW() WHERE id = %s",
                (photo_id,),
            )
        processed += 1

    conn.commit()
    cur.close()
    return processed


def safe_int(val):
    """Parse integer from EXIF, handling values like '1 5000'."""
    if val is None:
        return None
    if isinstance(val, int):
        return val
    try:
        return int(str(val).split()[0])
    except (ValueError, IndexError):
        return None


def read_exif(filepath):
    """Read EXIF using exiftool (most reliable for HEIC)."""
    try:
        result = subprocess.run(
            ["exiftool", "-json", "-n", filepath],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return None

        data = json.loads(result.stdout)
        if not data:
            return None
        d = data[0]

        # Date
        date_taken = None
        for key in ("DateTimeOriginal", "CreateDate", "ModifyDate"):
            val = d.get(key)
            if val and isinstance(val, str) and val.startswith("20"):
                date_taken = val.replace(":", "-", 2)
                break

        # GPS
        lat = d.get("GPSLatitude")
        lon = d.get("GPSLongitude")
        alt = d.get("GPSAltitude")
        gps_acc = d.get("GPSHPositioningError")

        return {
            "date_taken": date_taken,
            "camera_make": d.get("Make"),
            "camera_model": d.get("Model"),
            "lens_model": d.get("LensModel"),
            "focal_length": d.get("FocalLength"),
            "aperture": d.get("FNumber"),
            "shutter_speed": str(d.get("ExposureTime")) if d.get("ExposureTime") else None,
            "iso": safe_int(d.get("ISO")),
            "width": d.get("ImageWidth"),
            "height": d.get("ImageHeight"),
            "latitude": float(lat) if lat is not None else None,
            "longitude": float(lon) if lon is not None else None,
            "altitude": float(alt) if alt is not None else None,
            "gps_accuracy": float(gps_acc) if gps_acc is not None else None,
        }
    except Exception as e:
        print(f"  EXIF error {filepath}: {e}", file=sys.stderr)
        return None


def main():
    conn = get_db()
    print("=== EXIF Extraction ===")

    # Phase 1: scan new files
    print("Scanning photos...")
    new_count = scan_photos(conn)
    print(f"  {new_count} new photos registered")

    # Phase 2: extract EXIF in batches
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM photos WHERE exif_extracted = FALSE")
    remaining = cur.fetchone()[0]
    cur.close()
    print(f"  {remaining} photos to process")

    total = 0
    while True:
        processed = extract_exif_batch(conn, batch_size=50)
        if processed == 0:
            break
        total += processed
        print(f"  Processed {total}/{remaining}...", end="\r")

    print(f"\n  Done: {total} photos processed")

    # Stats
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM photos")
    total_photos = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM photos WHERE latitude IS NOT NULL")
    with_gps = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM photos WHERE date_taken IS NOT NULL")
    with_date = cur.fetchone()[0]
    cur.close()
    conn.close()

    print(f"\n  Total: {total_photos} photos")
    print(f"  With GPS: {with_gps}")
    print(f"  With date: {with_date}")


if __name__ == "__main__":
    main()
