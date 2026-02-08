import config


def collect():
    try:
        import psycopg2

        conn = psycopg2.connect(
            host=config.PG_HOST,
            port=config.PG_PORT,
            dbname=config.PG_DATABASE,
            user=config.PG_USER,
            password=config.PG_PASSWORD,
            connect_timeout=5,
        )
        cur = conn.cursor()

        # Global counts
        cur.execute("""
            SELECT
                COUNT(*) AS total,
                COUNT(CASE WHEN exif_extracted THEN 1 END) AS exif_done,
                COUNT(CASE WHEN clip_analyzed THEN 1 END) AS clip_done,
                COUNT(CASE WHEN yolo_analyzed THEN 1 END) AS yolo_done,
                COUNT(CASE WHEN face_analyzed THEN 1 END) AS face_done,
                COUNT(CASE WHEN latitude IS NOT NULL THEN 1 END) AS with_gps,
                COUNT(CASE WHEN date_taken IS NOT NULL THEN 1 END) AS with_date
            FROM photos
        """)
        row = cur.fetchone()
        totals = {
            "total_photos": row[0],
            "exif_done": row[1],
            "clip_done": row[2],
            "yolo_done": row[3],
            "face_done": row[4],
            "with_gps": row[5],
            "with_date": row[6],
        }

        # Tag counts
        cur.execute("""
            SELECT source, COUNT(*) FROM photo_tags GROUP BY source
        """)
        tag_counts = {row[0]: row[1] for row in cur.fetchall()}

        # Unique faces
        cur.execute("SELECT COUNT(DISTINCT id) FROM faces")
        unique_faces = cur.fetchone()[0]

        # Top CLIP tags
        cur.execute("""
            SELECT tag, COUNT(*) AS cnt, ROUND(AVG(score)::numeric, 2) AS avg_score
            FROM photo_tags WHERE source = 'clip'
            GROUP BY tag ORDER BY cnt DESC LIMIT 15
        """)
        top_clip_tags = [
            {"tag": row[0], "count": row[1], "avg_score": float(row[2])}
            for row in cur.fetchall()
        ]

        # Top YOLO detections
        cur.execute("""
            SELECT tag, COUNT(*) AS cnt, ROUND(AVG(score)::numeric, 2) AS avg_score
            FROM photo_tags WHERE source = 'yolo'
            GROUP BY tag ORDER BY cnt DESC LIMIT 15
        """)
        top_yolo_tags = [
            {"tag": row[0], "count": row[1], "avg_score": float(row[2])}
            for row in cur.fetchall()
        ]

        # Face clusters
        cur.execute("""
            SELECT f.id, f.cluster_label, f.age_estimate, f.gender_estimate,
                   COUNT(pf.id) AS photo_count
            FROM faces f
            JOIN photo_faces pf ON pf.face_id = f.id
            GROUP BY f.id, f.cluster_label, f.age_estimate, f.gender_estimate
            ORDER BY photo_count DESC
            LIMIT 20
        """)
        face_clusters = [
            {
                "face_id": row[0],
                "label": row[1] or f"Personne #{row[0]}",
                "age": row[2],
                "gender": row[3],
                "photo_count": row[4],
            }
            for row in cur.fetchall()
        ]

        cur.close()
        conn.close()

        return {
            "totals": totals,
            "tag_counts": tag_counts,
            "unique_faces": unique_faces,
            "top_clip_tags": top_clip_tags,
            "top_yolo_tags": top_yolo_tags,
            "face_clusters": face_clusters,
            "error": None,
        }
    except Exception as e:
        return {
            "totals": {},
            "tag_counts": {},
            "unique_faces": 0,
            "top_clip_tags": [],
            "top_yolo_tags": [],
            "face_clusters": [],
            "error": str(e),
        }
