"""Tag management: confirm, label, add, delete."""

from services.db import db_cursor


def confirm_tag(tag_id):
    """Toggle confirmed status of a tag."""
    with db_cursor() as cur:
        cur.execute("""
            UPDATE photo_tags SET confirmed = NOT confirmed
            WHERE id = %s RETURNING id, confirmed
        """, (tag_id,))
        row = cur.fetchone()
        if not row:
            return None
    return {"ok": True, "tag_id": row[0], "confirmed": row[1]}


def update_tag_label(tag_id, label):
    """Set custom label for a tag."""
    with db_cursor() as cur:
        cur.execute("""
            UPDATE photo_tags SET label = %s
            WHERE id = %s RETURNING id
        """, (label or None, tag_id))
        row = cur.fetchone()
        if not row:
            return None
    return {"ok": True, "tag_id": tag_id, "label": label}


def add_manual_tag(photo_id, tag, label=None, bbox=None):
    """Add a user-created tag with source='manual', score=1.0, confirmed=True.
       bbox is optional [x1, y1, x2, y2] in analysis space."""
    if bbox and len(bbox) == 4:
        bx1, by1, bx2, by2 = [int(c) for c in bbox]
    else:
        bx1 = by1 = bx2 = by2 = None

    with db_cursor() as cur:
        cur.execute("""
            INSERT INTO photo_tags (photo_id, tag, score, source, confirmed, label,
                                    bbox_x1, bbox_y1, bbox_x2, bbox_y2)
            VALUES (%s, %s, 1.0, 'manual', TRUE, %s, %s, %s, %s, %s)
            ON CONFLICT (photo_id, tag, source) DO NOTHING
            RETURNING id
        """, (photo_id, tag.strip().lower(), label, bx1, by1, bx2, by2))
        row = cur.fetchone()
        if not row:
            return {"ok": False, "error": "Ce tag existe déjà sur cette photo"}
    return {"ok": True, "tag_id": row[0], "tag": tag, "label": label}


def search_tags(q, limit=20):
    """Search existing tags by name for autocomplete."""
    with db_cursor() as cur:
        cur.execute("""
            SELECT tag, COUNT(*) as cnt
            FROM photo_tags
            WHERE tag ILIKE %s
            GROUP BY tag
            ORDER BY cnt DESC
            LIMIT %s
        """, (f"%{q}%", limit))
        return [{"tag": tag, "count": cnt} for tag, cnt in cur.fetchall()]


def delete_tag(tag_id):
    """Delete a tag (any source)."""
    with db_cursor() as cur:
        cur.execute("DELETE FROM photo_tags WHERE id = %s RETURNING id", (tag_id,))
        row = cur.fetchone()
        if not row:
            return None
    return {"ok": True, "tag_id": tag_id}
