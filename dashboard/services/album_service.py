"""Album management: list, create, update, delete, add/remove photos."""

from services.db import db_cursor


def list_albums(page=1, per_page=20):
    """List albums with photo counts."""
    per_page = min(per_page, 100)
    offset = (page - 1) * per_page

    with db_cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM albums")
        total = cur.fetchone()[0]

        cur.execute("""
            SELECT a.id, a.name, a.description, a.cover_photo_id,
                   a.created_at, a.updated_at,
                   COUNT(ap.id) AS photo_count
            FROM albums a
            LEFT JOIN album_photos ap ON ap.album_id = a.id
            GROUP BY a.id
            ORDER BY a.updated_at DESC
            LIMIT %s OFFSET %s
        """, (per_page, offset))

        albums = []
        for row in cur.fetchall():
            albums.append({
                "id": row[0],
                "name": row[1],
                "description": row[2],
                "cover_photo_id": row[3],
                "created_at": str(row[4]) if row[4] else None,
                "updated_at": str(row[5]) if row[5] else None,
                "photo_count": row[6],
            })

    return {"albums": albums, "total": total, "page": page, "per_page": per_page}


def create_album(name, description=None):
    """Create a new album."""
    with db_cursor() as cur:
        cur.execute("""
            INSERT INTO albums (name, description)
            VALUES (%s, %s) RETURNING id
        """, (name, description))
        album_id = cur.fetchone()[0]
    return {"ok": True, "album_id": album_id}


def get_album(album_id):
    """Get album details."""
    with db_cursor() as cur:
        cur.execute("""
            SELECT a.id, a.name, a.description, a.cover_photo_id,
                   a.created_at, a.updated_at,
                   COUNT(ap.id) AS photo_count
            FROM albums a
            LEFT JOIN album_photos ap ON ap.album_id = a.id
            WHERE a.id = %s
            GROUP BY a.id
        """, (album_id,))
        row = cur.fetchone()
        if not row:
            return None
        return {
            "id": row[0],
            "name": row[1],
            "description": row[2],
            "cover_photo_id": row[3],
            "created_at": str(row[4]) if row[4] else None,
            "updated_at": str(row[5]) if row[5] else None,
            "photo_count": row[6],
        }


def update_album(album_id, name=None, description=None, cover_photo_id=None):
    """Update album name, description, or cover."""
    sets = []
    params = []
    if name is not None:
        sets.append("name = %s")
        params.append(name)
    if description is not None:
        sets.append("description = %s")
        params.append(description)
    if cover_photo_id is not None:
        sets.append("cover_photo_id = %s")
        params.append(cover_photo_id if cover_photo_id > 0 else None)
    if not sets:
        return None

    sets.append("updated_at = NOW()")
    params.append(album_id)

    with db_cursor() as cur:
        cur.execute(f"""
            UPDATE albums SET {', '.join(sets)}
            WHERE id = %s RETURNING id
        """, params)
        row = cur.fetchone()
        if not row:
            return None
    return {"ok": True}


def delete_album(album_id):
    """Delete an album (CASCADE removes album_photos)."""
    with db_cursor() as cur:
        cur.execute("DELETE FROM albums WHERE id = %s RETURNING id", (album_id,))
        row = cur.fetchone()
        if not row:
            return None
    return {"ok": True}


def get_album_photos(album_id, page=1, per_page=50):
    """Get photos in an album."""
    per_page = min(per_page, 200)
    offset = (page - 1) * per_page

    with db_cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM album_photos WHERE album_id = %s", (album_id,))
        total = cur.fetchone()[0]

        cur.execute("""
            SELECT p.id, p.filename, p.filepath, p.date_taken, p.camera_model,
                   p.latitude, p.longitude, p.width, p.height, ap.added_at
            FROM photos p
            JOIN album_photos ap ON ap.photo_id = p.id
            WHERE ap.album_id = %s
            ORDER BY ap.added_at DESC
            LIMIT %s OFFSET %s
        """, (album_id, per_page, offset))

        columns = [desc[0] for desc in cur.description]
        photos = []
        for row in cur.fetchall():
            photo = dict(zip(columns, row))
            photo["thumb_url"] = f"/api/explorer/photo/{photo['id']}/thumb"
            photo["added_at"] = str(photo["added_at"]) if photo.get("added_at") else None
            if photo["latitude"]:
                photo["latitude"] = float(photo["latitude"])
            if photo["longitude"]:
                photo["longitude"] = float(photo["longitude"])
            photos.append(photo)

    return {"photos": photos, "total": total, "page": page, "per_page": per_page}


def add_photos_to_album(album_id, photo_ids):
    """Add photos to album. Returns count of actually added."""
    added = 0
    with db_cursor() as cur:
        cur.execute("SELECT id FROM albums WHERE id = %s", (album_id,))
        if not cur.fetchone():
            return {"ok": False, "error": "Album introuvable"}

        for pid in photo_ids:
            cur.execute("""
                INSERT INTO album_photos (album_id, photo_id)
                VALUES (%s, %s)
                ON CONFLICT (album_id, photo_id) DO NOTHING
                RETURNING id
            """, (album_id, pid))
            if cur.fetchone():
                added += 1

        cur.execute("UPDATE albums SET updated_at = NOW() WHERE id = %s", (album_id,))

    return {"ok": True, "added": added}


def remove_photo_from_album(album_id, photo_id):
    """Remove a photo from an album."""
    with db_cursor() as cur:
        cur.execute("""
            DELETE FROM album_photos
            WHERE album_id = %s AND photo_id = %s RETURNING id
        """, (album_id, photo_id))
        row = cur.fetchone()
        if not row:
            return None
        cur.execute("UPDATE albums SET updated_at = NOW() WHERE id = %s", (album_id,))
    return {"ok": True}


def get_photo_albums(photo_id):
    """Get albums containing a specific photo."""
    with db_cursor() as cur:
        cur.execute("""
            SELECT a.id, a.name FROM albums a
            JOIN album_photos ap ON ap.album_id = a.id
            WHERE ap.photo_id = %s
            ORDER BY a.name
        """, (photo_id,))
        return [{"id": aid, "name": name} for aid, name in cur.fetchall()]
