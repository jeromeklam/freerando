#!/usr/bin/env python3
"""Analyze photos with CLIP, YOLO and InsightFace, store results in PostgreSQL."""

import os
import sys
import time
import struct
import numpy as np
import psycopg2
import config

# Lazy-loaded models
_clip_model = None
_clip_preprocess = None
_clip_tokenizer = None
_clip_text_features = None
_yolo_model = None
_face_app = None


def get_db():
    return psycopg2.connect(
        host=config.PG_HOST,
        port=config.PG_PORT,
        dbname=config.PG_DATABASE,
        user=config.PG_USER,
        password=config.PG_PASSWORD,
    )


def load_image(filepath):
    """Load image as PIL and numpy array."""
    import pillow_heif
    pillow_heif.register_heif_opener()
    from PIL import Image

    img = Image.open(filepath).convert("RGB")
    # Resize if too large (save memory on Pi)
    max_dim = 2048
    if max(img.size) > max_dim:
        ratio = max_dim / max(img.size)
        new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
        img = img.resize(new_size)
    return img, np.array(img)


# --- CLIP ---
def get_clip():
    global _clip_model, _clip_preprocess, _clip_tokenizer, _clip_text_features
    if _clip_model is None:
        import open_clip
        import torch

        print("  Loading CLIP model...")
        _clip_model, _, _clip_preprocess = open_clip.create_model_and_transforms(
            config.CLIP_MODEL, pretrained=config.CLIP_PRETRAINED
        )
        _clip_tokenizer = open_clip.tokenize
        # Pre-compute text embeddings
        text = _clip_tokenizer(config.CLIP_TAGS)
        with torch.no_grad():
            _clip_text_features = _clip_model.encode_text(text)
            _clip_text_features /= _clip_text_features.norm(dim=-1, keepdim=True)
        print("  CLIP ready")
    return _clip_model, _clip_preprocess, _clip_text_features


def analyze_clip(img_pil):
    """Return list of (tag, score) above threshold."""
    import torch

    model, preprocess, text_features = get_clip()
    image = preprocess(img_pil).unsqueeze(0)

    with torch.no_grad():
        image_features = model.encode_image(image)
        image_features /= image_features.norm(dim=-1, keepdim=True)
        similarity = (image_features @ text_features.T).squeeze(0)

    results = []
    for tag, score in zip(config.CLIP_TAGS, similarity.tolist()):
        if score >= config.CLIP_THRESHOLD:
            results.append((tag, round(score, 3)))

    results.sort(key=lambda x: x[1], reverse=True)
    return results[:10]  # top 10 tags


# --- YOLO ---
def get_yolo():
    global _yolo_model
    if _yolo_model is None:
        from ultralytics import YOLO

        print("  Loading YOLO model...")
        _yolo_model = YOLO(config.YOLO_MODEL)
        print("  YOLO ready")
    return _yolo_model


def analyze_yolo(filepath):
    """Return list of (label, confidence)."""
    model = get_yolo()
    results = model(filepath, verbose=False, conf=config.YOLO_CONFIDENCE)

    detections = []
    seen = set()
    for r in results:
        for box in r.boxes:
            cls = int(box.cls[0])
            conf = float(box.conf[0])
            label = model.names[cls]
            if label not in seen:
                detections.append((label, round(conf, 3)))
                seen.add(label)

    detections.sort(key=lambda x: x[1], reverse=True)
    return detections


# --- InsightFace ---
def get_face_app():
    global _face_app
    if _face_app is None:
        from insightface.app import FaceAnalysis

        print("  Loading InsightFace model...")
        _face_app = FaceAnalysis(
            name=config.INSIGHTFACE_MODEL,
            providers=["CPUExecutionProvider"],
        )
        _face_app.prepare(ctx_id=0, det_size=config.INSIGHTFACE_DET_SIZE)
        print("  InsightFace ready")
    return _face_app


def analyze_faces(img_np):
    """Return list of face dicts with bbox, embedding, age, gender."""
    app = get_face_app()
    img_bgr = img_np[:, :, ::-1]
    faces = app.get(img_bgr)

    results = []
    for face in faces:
        results.append({
            "bbox": face.bbox.astype(int).tolist(),
            "embedding": face.embedding,
            "age": int(face.age),
            "gender": "M" if face.gender == 1 else "F",
        })
    return results


def embedding_to_bytes(embedding):
    """Convert numpy float32 array to bytes."""
    return embedding.astype(np.float32).tobytes()


def find_matching_face(conn, embedding, threshold=None):
    """Find existing face by cosine similarity."""
    if threshold is None:
        threshold = config.FACE_SIMILARITY_THRESHOLD

    cur = conn.cursor()
    cur.execute("SELECT id, embedding FROM faces")
    rows = cur.fetchall()
    cur.close()

    if not rows:
        return None

    query_norm = embedding / np.linalg.norm(embedding)

    best_id = None
    best_score = -1

    for face_id, emb_bytes in rows:
        stored = np.frombuffer(emb_bytes, dtype=np.float32)
        stored_norm = stored / np.linalg.norm(stored)
        score = float(np.dot(query_norm, stored_norm))
        if score > best_score:
            best_score = score
            best_id = face_id

    if best_score >= threshold:
        return best_id
    return None


# --- Main batch processing ---
def process_clip_batch(conn, batch_size=50):
    """Process photos with CLIP that haven't been analyzed yet."""
    cur = conn.cursor()
    cur.execute(
        """SELECT id, filepath FROM photos
           WHERE clip_analyzed = FALSE AND exif_extracted = TRUE
           AND extension IN ('.HEIC', '.JPG', '.JPEG', '.PNG')
           ORDER BY id LIMIT %s""",
        (batch_size,),
    )
    rows = cur.fetchall()

    if not rows:
        return 0

    processed = 0
    for photo_id, relpath in rows:
        fullpath = os.path.join(config.PHOTOS_ROOT, relpath)
        if not os.path.exists(fullpath):
            cur.execute("UPDATE photos SET clip_analyzed = TRUE WHERE id = %s", (photo_id,))
            continue

        try:
            img_pil, _ = load_image(fullpath)
            tags = analyze_clip(img_pil)

            for tag, score in tags:
                cur.execute(
                    """INSERT INTO photo_tags (photo_id, tag, score, source)
                       VALUES (%s, %s, %s, 'clip')""",
                    (photo_id, tag, score),
                )

            cur.execute(
                "UPDATE photos SET clip_analyzed = TRUE, updated_at = NOW() WHERE id = %s",
                (photo_id,),
            )
            processed += 1
        except Exception as e:
            print(f"\n  CLIP error {relpath}: {e}", file=sys.stderr)
            cur.execute("UPDATE photos SET clip_analyzed = TRUE WHERE id = %s", (photo_id,))

    conn.commit()
    cur.close()
    return processed


def process_yolo_batch(conn, batch_size=50):
    """Process photos with YOLO that haven't been analyzed yet."""
    cur = conn.cursor()
    cur.execute(
        """SELECT id, filepath FROM photos
           WHERE yolo_analyzed = FALSE AND exif_extracted = TRUE
           AND extension IN ('.HEIC', '.JPG', '.JPEG', '.PNG')
           ORDER BY id LIMIT %s""",
        (batch_size,),
    )
    rows = cur.fetchall()

    if not rows:
        return 0

    processed = 0
    for photo_id, relpath in rows:
        fullpath = os.path.join(config.PHOTOS_ROOT, relpath)
        if not os.path.exists(fullpath):
            cur.execute("UPDATE photos SET yolo_analyzed = TRUE WHERE id = %s", (photo_id,))
            continue

        try:
            detections = analyze_yolo(fullpath)

            for label, conf in detections:
                cur.execute(
                    """INSERT INTO photo_tags (photo_id, tag, score, source)
                       VALUES (%s, %s, %s, 'yolo')""",
                    (photo_id, label, conf),
                )

            cur.execute(
                "UPDATE photos SET yolo_analyzed = TRUE, updated_at = NOW() WHERE id = %s",
                (photo_id,),
            )
            processed += 1
        except Exception as e:
            print(f"\n  YOLO error {relpath}: {e}", file=sys.stderr)
            cur.execute("UPDATE photos SET yolo_analyzed = TRUE WHERE id = %s", (photo_id,))

    conn.commit()
    cur.close()
    return processed


def process_faces_batch(conn, batch_size=20):
    """Process photos with InsightFace."""
    cur = conn.cursor()
    cur.execute(
        """SELECT id, filepath FROM photos
           WHERE face_analyzed = FALSE AND exif_extracted = TRUE
           AND extension IN ('.HEIC', '.JPG', '.JPEG', '.PNG')
           ORDER BY id LIMIT %s""",
        (batch_size,),
    )
    rows = cur.fetchall()

    if not rows:
        return 0

    processed = 0
    for photo_id, relpath in rows:
        fullpath = os.path.join(config.PHOTOS_ROOT, relpath)
        if not os.path.exists(fullpath):
            cur.execute("UPDATE photos SET face_analyzed = TRUE WHERE id = %s", (photo_id,))
            continue

        try:
            _, img_np = load_image(fullpath)
            faces = analyze_faces(img_np)

            for face_data in faces:
                emb_bytes = embedding_to_bytes(face_data["embedding"])

                # Try to match existing face
                face_id = find_matching_face(conn, face_data["embedding"])

                if face_id is None:
                    # New face
                    cur.execute(
                        """INSERT INTO faces (embedding, age_estimate, gender_estimate)
                           VALUES (%s, %s, %s) RETURNING id""",
                        (psycopg2.Binary(emb_bytes), face_data["age"], face_data["gender"]),
                    )
                    face_id = cur.fetchone()[0]

                bbox = face_data["bbox"]
                cur.execute(
                    """INSERT INTO photo_faces (photo_id, face_id, bbox_x1, bbox_y1, bbox_x2, bbox_y2, confidence)
                       VALUES (%s, %s, %s, %s, %s, %s, 1.0)""",
                    (photo_id, face_id, bbox[0], bbox[1], bbox[2], bbox[3]),
                )

            cur.execute(
                "UPDATE photos SET face_analyzed = TRUE, updated_at = NOW() WHERE id = %s",
                (photo_id,),
            )
            processed += 1
        except Exception as e:
            print(f"\n  Face error {relpath}: {e}", file=sys.stderr)
            cur.execute("UPDATE photos SET face_analyzed = TRUE WHERE id = %s", (photo_id,))

    conn.commit()
    cur.close()
    return processed


def main():
    conn = get_db()

    # Count pending
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM photos WHERE exif_extracted = TRUE AND clip_analyzed = FALSE AND extension IN ('.HEIC', '.JPG', '.JPEG', '.PNG')")
    clip_pending = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM photos WHERE exif_extracted = TRUE AND yolo_analyzed = FALSE AND extension IN ('.HEIC', '.JPG', '.JPEG', '.PNG')")
    yolo_pending = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM photos WHERE exif_extracted = TRUE AND face_analyzed = FALSE AND extension IN ('.HEIC', '.JPG', '.JPEG', '.PNG')")
    face_pending = cur.fetchone()[0]
    cur.close()

    print("=== Photo Analysis ===")
    print(f"  CLIP pending: {clip_pending}")
    print(f"  YOLO pending: {yolo_pending}")
    print(f"  Faces pending: {face_pending}")

    # Process in rounds
    total_clip = 0
    total_yolo = 0
    total_face = 0
    start = time.time()

    while True:
        did_work = False

        n = process_clip_batch(conn, batch_size=20)
        total_clip += n
        if n > 0:
            did_work = True

        n = process_yolo_batch(conn, batch_size=20)
        total_yolo += n
        if n > 0:
            did_work = True

        n = process_faces_batch(conn, batch_size=10)
        total_face += n
        if n > 0:
            did_work = True

        if not did_work:
            break

        elapsed = time.time() - start
        rate = (total_clip + total_yolo + total_face) / elapsed if elapsed > 0 else 0
        print(
            f"  CLIP: {total_clip}/{clip_pending}  "
            f"YOLO: {total_yolo}/{yolo_pending}  "
            f"Faces: {total_face}/{face_pending}  "
            f"({rate:.1f} ops/s)   ",
            end="\r",
        )

    elapsed = time.time() - start
    print(f"\n\nDone in {elapsed:.0f}s")
    print(f"  CLIP: {total_clip} photos tagged")
    print(f"  YOLO: {total_yolo} photos analyzed")
    print(f"  Faces: {total_face} photos scanned")

    # Final stats
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM photo_tags WHERE source = 'clip'")
    print(f"  Total CLIP tags: {cur.fetchone()[0]}")
    cur.execute("SELECT COUNT(*) FROM photo_tags WHERE source = 'yolo'")
    print(f"  Total YOLO detections: {cur.fetchone()[0]}")
    cur.execute("SELECT COUNT(DISTINCT id) FROM faces")
    print(f"  Unique faces: {cur.fetchone()[0]}")
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
