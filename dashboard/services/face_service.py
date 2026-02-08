"""Face management: list, rename, merge, crop."""

from services.db import db_cursor


def list_faces(page=1, per_page=20):
    """List face clusters with photo counts and sample photos."""
    per_page = min(per_page, 100)
    offset = (page - 1) * per_page

    with db_cursor() as cur:
        # Total count
        cur.execute("SELECT COUNT(*) FROM faces")
        total = cur.fetchone()[0]

        # Face clusters
        cur.execute("""
            SELECT f.id, f.cluster_label, f.age_estimate, f.gender_estimate,
                   COUNT(pf.id) AS photo_count, f.face_type
            FROM faces f
            LEFT JOIN photo_faces pf ON pf.face_id = f.id
            GROUP BY f.id
            ORDER BY photo_count DESC
            LIMIT %s OFFSET %s
        """, (per_page, offset))

        faces = []
        for fid, label, age, gender, count, face_type in cur.fetchall():
            faces.append({
                "id": fid,
                "label": label or f"Personne #{fid}",
                "age_estimate": age,
                "gender_estimate": gender,
                "photo_count": count,
                "face_type": face_type,
            })

        # Get sample photos for each face (first 3)
        if faces:
            face_ids = [f["id"] for f in faces]
            cur.execute("""
                SELECT DISTINCT ON (pf.face_id) pf.face_id, pf.photo_id,
                       pf.bbox_x1, pf.bbox_y1, pf.bbox_x2, pf.bbox_y2
                FROM photo_faces pf
                WHERE pf.face_id = ANY(%s)
                ORDER BY pf.face_id, pf.id
            """, (face_ids,))

            samples = {}
            for face_id, photo_id, x1, y1, x2, y2 in cur.fetchall():
                samples.setdefault(face_id, []).append({
                    "photo_id": photo_id,
                    "bbox": [x1, y1, x2, y2]
                })

            for f in faces:
                f["sample_photos"] = samples.get(f["id"], [])

    return {"faces": faces, "total": total, "page": page, "per_page": per_page}


def get_face_photos(face_id, page=1, per_page=50):
    """Get all photos containing a specific face."""
    per_page = min(per_page, 200)
    offset = (page - 1) * per_page

    with db_cursor() as cur:
        cur.execute("""
            SELECT COUNT(DISTINCT photo_id) FROM photo_faces WHERE face_id = %s
        """, (face_id,))
        total = cur.fetchone()[0]

        cur.execute("""
            SELECT DISTINCT p.id, p.filename, p.filepath, p.date_taken, p.camera_model,
                   p.latitude, p.longitude, p.width, p.height
            FROM photos p
            JOIN photo_faces pf ON pf.photo_id = p.id
            WHERE pf.face_id = %s
            ORDER BY p.date_taken DESC NULLS LAST
            LIMIT %s OFFSET %s
        """, (face_id, per_page, offset))

        columns = [desc[0] for desc in cur.description]
        photos = []
        for row in cur.fetchall():
            photo = dict(zip(columns, row))
            photo["thumb_url"] = f"/api/explorer/photo/{photo['id']}/thumb"
            if photo["latitude"]:
                photo["latitude"] = float(photo["latitude"])
            if photo["longitude"]:
                photo["longitude"] = float(photo["longitude"])
            photos.append(photo)

    return {"photos": photos, "total": total, "page": page, "per_page": per_page}


def rename_face(face_id, label):
    """Rename a face cluster."""
    with db_cursor() as cur:
        cur.execute("""
            UPDATE faces SET cluster_label = %s
            WHERE id = %s RETURNING id
        """, (label, face_id))
        row = cur.fetchone()
        if not row:
            return None
    return {"ok": True, "face_id": face_id, "label": label}


def update_face_type(face_id, face_type):
    """Update the face type (personne, animal, objet, or None)."""
    valid_types = ('personne', 'animal', 'objet', None)
    if face_type not in valid_types:
        return {"ok": False, "error": "Type invalide"}
    with db_cursor() as cur:
        cur.execute("""
            UPDATE faces SET face_type = %s
            WHERE id = %s RETURNING id
        """, (face_type, face_id))
        row = cur.fetchone()
        if not row:
            return None
    return {"ok": True, "face_id": face_id, "face_type": face_type}


def merge_faces(source_ids, target_id):
    """Merge face clusters into target. Updates photo_faces, deletes sources."""
    if target_id in source_ids:
        source_ids = [sid for sid in source_ids if sid != target_id]
    if not source_ids:
        return {"ok": False, "error": "No source faces to merge"}

    with db_cursor() as cur:
        # Update photo_faces to point to target
        for sid in source_ids:
            # Avoid duplicates: delete if photo already has target face
            cur.execute("""
                DELETE FROM photo_faces
                WHERE face_id = %s AND photo_id IN (
                    SELECT photo_id FROM photo_faces WHERE face_id = %s
                )
            """, (sid, target_id))

            cur.execute("""
                UPDATE photo_faces SET face_id = %s WHERE face_id = %s
            """, (target_id, sid))

        # Delete source face records
        cur.execute("""
            DELETE FROM faces WHERE id = ANY(%s)
        """, (source_ids,))

        # Get new photo count
        cur.execute("""
            SELECT COUNT(*) FROM photo_faces WHERE face_id = %s
        """, (target_id,))
        new_count = cur.fetchone()[0]

    return {
        "ok": True,
        "merged": len(source_ids),
        "target_id": target_id,
        "new_photo_count": new_count
    }


def assign_face_to_photo(photo_id, face_id, bbox=None):
    """Manually assign an existing face to a photo, optionally with bounding box."""
    with db_cursor() as cur:
        cur.execute("SELECT id FROM faces WHERE id = %s", (face_id,))
        if not cur.fetchone():
            return {"ok": False, "error": "Visage introuvable"}

        cur.execute("""
            SELECT id FROM photo_faces WHERE photo_id = %s AND face_id = %s
        """, (photo_id, face_id))
        if cur.fetchone():
            return {"ok": False, "error": "Visage déjà assigné à cette photo"}

        if bbox and len(bbox) == 4:
            x1, y1, x2, y2 = [int(c) for c in bbox]
            confidence = 0.5
        else:
            x1, y1, x2, y2 = 0, 0, 0, 0
            confidence = 0.0

        cur.execute("""
            INSERT INTO photo_faces (photo_id, face_id, bbox_x1, bbox_y1, bbox_x2, bbox_y2, confidence)
            VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id
        """, (photo_id, face_id, x1, y1, x2, y2, confidence))
        pf_id = cur.fetchone()[0]

    return {"ok": True, "photo_face_id": pf_id}


def create_face(label):
    """Create a new face identity by name (manual, no embedding)."""
    with db_cursor() as cur:
        cur.execute("""
            INSERT INTO faces (cluster_label)
            VALUES (%s) RETURNING id
        """, (label,))
        face_id = cur.fetchone()[0]
    return {"ok": True, "face_id": face_id, "label": label}


def remove_face_from_photo(photo_id, face_id):
    """Remove a face-photo association."""
    with db_cursor() as cur:
        cur.execute("""
            DELETE FROM photo_faces WHERE photo_id = %s AND face_id = %s RETURNING id
        """, (photo_id, face_id))
        row = cur.fetchone()
        if not row:
            return None
    return {"ok": True}


def search_faces(q, limit=20):
    """Search faces by label for autocomplete."""
    with db_cursor() as cur:
        cur.execute("""
            SELECT f.id, f.cluster_label, COUNT(pf.id) as photo_count
            FROM faces f
            LEFT JOIN photo_faces pf ON pf.face_id = f.id
            WHERE f.cluster_label ILIKE %s
            GROUP BY f.id
            ORDER BY photo_count DESC
            LIMIT %s
        """, (f"%{q}%", limit))
        return [{"id": fid, "label": label or f"Personne #{fid}", "photo_count": cnt}
                for fid, label, cnt in cur.fetchall()]


def get_face_crop_info(face_id):
    """Get info needed to generate a face crop."""
    with db_cursor() as cur:
        cur.execute("""
            SELECT p.filepath, pf.photo_id, pf.bbox_x1, pf.bbox_y1, pf.bbox_x2, pf.bbox_y2
            FROM photo_faces pf
            JOIN photos p ON p.id = pf.photo_id
            WHERE pf.face_id = %s
            ORDER BY pf.id LIMIT 1
        """, (face_id,))
        row = cur.fetchone()
        if not row:
            return None
        return {
            "filepath": row[0],
            "photo_id": row[1],
            "bbox": [row[2], row[3], row[4], row[5]]
        }
