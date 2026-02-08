"""Photo search and filter queries."""

from services.db import db_cursor


def search_photos(tag=None, source=None, date_from=None, date_to=None,
                  camera=None, face_id=None, q=None, has_gps=False,
                  sort="date_taken", order="desc", page=1, per_page=50):
    """Search photos with combined filters. Returns (photos, total)."""
    per_page = min(per_page, 200)
    offset = (page - 1) * per_page

    conditions = []
    params = []

    if tag:
        conditions.append(
            "p.id IN (SELECT pt.photo_id FROM photo_tags pt WHERE pt.tag = %s"
            + (" AND pt.source = %s" if source else "")
            + ")"
        )
        params.append(tag)
        if source:
            params.append(source)

    if date_from:
        conditions.append("p.date_taken >= %s")
        params.append(date_from)

    if date_to:
        conditions.append("p.date_taken <= %s")
        params.append(date_to + " 23:59:59")

    if camera:
        conditions.append("p.camera_model = %s")
        params.append(camera)

    if face_id:
        conditions.append(
            "p.id IN (SELECT pf.photo_id FROM photo_faces pf WHERE pf.face_id = %s)"
        )
        params.append(face_id)

    if q:
        conditions.append("p.filename ILIKE %s")
        params.append(f"%{q}%")

    if has_gps:
        conditions.append("p.latitude IS NOT NULL")

    where = " AND ".join(conditions) if conditions else "1=1"

    # Validate sort/order
    allowed_sorts = {"date_taken", "filename", "filesize", "id"}
    if sort not in allowed_sorts:
        sort = "date_taken"
    if order not in ("asc", "desc"):
        order = "desc"

    nulls = "NULLS LAST" if order == "desc" else "NULLS FIRST"

    with db_cursor() as cur:
        # Count total
        cur.execute(f"SELECT COUNT(*) FROM photos p WHERE {where}", params)
        total = cur.fetchone()[0]

        # Fetch page
        cur.execute(f"""
            SELECT p.id, p.filename, p.filepath, p.extension, p.filesize,
                   p.date_taken, p.camera_model, p.width, p.height,
                   p.latitude, p.longitude, p.altitude
            FROM photos p
            WHERE {where}
            ORDER BY p.{sort} {order} {nulls}
            LIMIT %s OFFSET %s
        """, params + [per_page, offset])

        columns = [desc[0] for desc in cur.description]
        photos = [dict(zip(columns, row)) for row in cur.fetchall()]

        # Get tags for these photos
        if photos:
            photo_ids = [p["id"] for p in photos]
            cur.execute("""
                SELECT photo_id, id, tag, score, source, confirmed, label
                FROM photo_tags
                WHERE photo_id = ANY(%s)
                ORDER BY confirmed DESC, score DESC
            """, (photo_ids,))
            tags_by_photo = {}
            for pid, tid, tag, score, src, conf, lbl in cur.fetchall():
                tags_by_photo.setdefault(pid, []).append({
                    "id": tid, "tag": tag, "score": float(score),
                    "source": src, "confirmed": conf, "label": lbl
                })

            # Get face count per photo
            cur.execute("""
                SELECT photo_id, COUNT(*) FROM photo_faces
                WHERE photo_id = ANY(%s)
                GROUP BY photo_id
            """, (photo_ids,))
            face_counts = dict(cur.fetchall())

            for p in photos:
                p["tags"] = tags_by_photo.get(p["id"], [])
                p["face_count"] = face_counts.get(p["id"], 0)
                p["thumb_url"] = f"/api/explorer/photo/{p['id']}/thumb"
                if p["filesize"]:
                    p["filesize"] = int(p["filesize"])
                if p["latitude"]:
                    p["latitude"] = float(p["latitude"])
                if p["longitude"]:
                    p["longitude"] = float(p["longitude"])
                if p["altitude"]:
                    p["altitude"] = float(p["altitude"])

    return photos, total


def get_photo_detail(photo_id):
    """Get full photo details including tags and faces."""
    with db_cursor() as cur:
        cur.execute("""
            SELECT id, filename, filepath, extension, filesize,
                   date_taken, camera_make, camera_model, lens_model,
                   focal_length, aperture, shutter_speed, iso,
                   width, height, latitude, longitude, altitude
            FROM photos WHERE id = %s
        """, (photo_id,))
        row = cur.fetchone()
        if not row:
            return None

        columns = [desc[0] for desc in cur.description]
        photo = dict(zip(columns, row))

        # Float conversions
        for key in ("filesize", "focal_length", "aperture", "latitude",
                     "longitude", "altitude"):
            if photo.get(key) is not None:
                photo[key] = float(photo[key])

        # Tags (with optional bbox)
        cur.execute("""
            SELECT id, tag, score, source, confirmed, label,
                   bbox_x1, bbox_y1, bbox_x2, bbox_y2
            FROM photo_tags
            WHERE photo_id = %s ORDER BY confirmed DESC, score DESC
        """, (photo_id,))
        photo["tags"] = [
            {"id": tid, "tag": t, "score": float(s), "source": src,
             "confirmed": conf, "label": lbl,
             "bbox": [bx1, by1, bx2, by2] if bx1 is not None else None}
            for tid, t, s, src, conf, lbl, bx1, by1, bx2, by2 in cur.fetchall()
        ]

        # Faces (with face_type)
        cur.execute("""
            SELECT pf.face_id, f.cluster_label, f.age_estimate, f.gender_estimate,
                   pf.bbox_x1, pf.bbox_y1, pf.bbox_x2, pf.bbox_y2, pf.confidence,
                   f.face_type
            FROM photo_faces pf
            JOIN faces f ON f.id = pf.face_id
            WHERE pf.photo_id = %s
        """, (photo_id,))
        photo["faces"] = [
            {
                "face_id": fid,
                "label": label or f"Personne #{fid}",
                "age": age, "gender": gender,
                "bbox": [x1, y1, x2, y2],
                "confidence": float(conf),
                "face_type": face_type,
            }
            for fid, label, age, gender, x1, y1, x2, y2, conf, face_type in cur.fetchall()
        ]

    return photo


def get_geo_photos(tag=None, date_from=None, date_to=None):
    """Get all geolocated photos as GeoJSON."""
    conditions = ["p.latitude IS NOT NULL"]
    params = []

    if tag:
        conditions.append(
            "p.id IN (SELECT pt.photo_id FROM photo_tags pt WHERE pt.tag = %s)"
        )
        params.append(tag)

    if date_from:
        conditions.append("p.date_taken >= %s")
        params.append(date_from)

    if date_to:
        conditions.append("p.date_taken <= %s")
        params.append(date_to + " 23:59:59")

    where = " AND ".join(conditions)

    with db_cursor() as cur:
        cur.execute(f"""
            SELECT p.id, p.filename, p.latitude, p.longitude, p.date_taken, p.camera_model
            FROM photos p
            WHERE {where}
            ORDER BY p.date_taken DESC NULLS LAST
            LIMIT 5000
        """, params)

        features = []
        for pid, fname, lat, lon, dt, cam in cur.fetchall():
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [float(lon), float(lat)]
                },
                "properties": {
                    "id": pid,
                    "filename": fname,
                    "date_taken": str(dt) if dt else None,
                    "camera_model": cam
                }
            })

    return {"type": "FeatureCollection", "features": features}


def get_filters():
    """Get available filter options for dropdowns."""
    with db_cursor() as cur:
        # Cameras
        cur.execute("""
            SELECT camera_model, COUNT(*) FROM photos
            WHERE camera_model IS NOT NULL
            GROUP BY camera_model ORDER BY COUNT(*) DESC
        """)
        cameras = [{"model": m, "count": c} for m, c in cur.fetchall()]

        # CLIP tags
        cur.execute("""
            SELECT tag, COUNT(*) FROM photo_tags
            WHERE source = 'clip'
            GROUP BY tag ORDER BY COUNT(*) DESC LIMIT 50
        """)
        clip_tags = [{"tag": t, "count": c} for t, c in cur.fetchall()]

        # YOLO tags
        cur.execute("""
            SELECT tag, COUNT(*) FROM photo_tags
            WHERE source = 'yolo'
            GROUP BY tag ORDER BY COUNT(*) DESC LIMIT 50
        """)
        yolo_tags = [{"tag": t, "count": c} for t, c in cur.fetchall()]

        # Years
        cur.execute("""
            SELECT DISTINCT EXTRACT(YEAR FROM date_taken::timestamp)::int
            FROM photos WHERE date_taken IS NOT NULL
            ORDER BY 1
        """)
        years = [row[0] for row in cur.fetchall()]

        # Totals
        cur.execute("""
            SELECT COUNT(*),
                   COUNT(CASE WHEN latitude IS NOT NULL THEN 1 END),
                   COUNT(CASE WHEN face_analyzed AND id IN (SELECT photo_id FROM photo_faces) THEN 1 END)
            FROM photos
        """)
        total, geolocated, with_faces = cur.fetchone()

    return {
        "cameras": cameras,
        "tags": {"clip": clip_tags, "yolo": yolo_tags},
        "years": years,
        "total_photos": total,
        "total_geolocated": geolocated,
        "total_with_faces": with_faces,
    }
