"""CLIP text-to-image search: encode query text and find similar photos."""

import time
import threading
import numpy as np
from services.db import db_cursor

# Cache
_embeddings_cache = None  # dict: photo_id -> normalized float32 array
_cache_time = 0
_cache_lock = threading.Lock()
CACHE_TTL = 600  # 10 minutes

# CLIP model (lazy loaded)
_clip_model = None
_clip_tokenizer = None
_model_lock = threading.Lock()


def _load_model():
    """Lazy-load CLIP model for text encoding only."""
    global _clip_model, _clip_tokenizer
    if _clip_model is not None:
        return

    with _model_lock:
        if _clip_model is not None:
            return
        import open_clip
        print("[CLIP Search] Loading model...")
        _clip_model, _, _ = open_clip.create_model_and_transforms(
            "ViT-B-32", pretrained="laion2b_s34b_b79k"
        )
        _clip_tokenizer = open_clip.tokenize
        print("[CLIP Search] Model ready")


def _load_embeddings():
    """Load all photo embeddings from DB into RAM cache."""
    global _embeddings_cache, _cache_time

    with _cache_lock:
        if _embeddings_cache is not None and (time.time() - _cache_time) < CACHE_TTL:
            return _embeddings_cache

    print("[CLIP Search] Loading embeddings cache...")
    embeddings = {}
    with db_cursor() as cur:
        cur.execute("""
            SELECT id, clip_embedding FROM photos
            WHERE clip_embedding IS NOT NULL AND length(clip_embedding) > 0
        """)
        for photo_id, emb_bytes in cur.fetchall():
            try:
                emb = np.frombuffer(bytes(emb_bytes), dtype=np.float32)
                if len(emb) > 0:
                    norm = np.linalg.norm(emb)
                    if norm > 0:
                        embeddings[photo_id] = emb / norm
            except Exception:
                pass

    with _cache_lock:
        _embeddings_cache = embeddings
        _cache_time = time.time()

    print(f"[CLIP Search] Cached {len(embeddings)} embeddings")
    return embeddings


def search_by_text(query, limit=50):
    """Search photos by text query using CLIP cosine similarity.

    Returns list of {"photo_id": int, "score": float} sorted by score desc.
    """
    import torch

    _load_model()
    embeddings = _load_embeddings()

    if not embeddings:
        return []

    # Encode text query
    tokens = _clip_tokenizer([query])
    with torch.no_grad():
        text_features = _clip_model.encode_text(tokens)
        text_features /= text_features.norm(dim=-1, keepdim=True)

    query_vec = text_features.squeeze(0).cpu().numpy().astype(np.float32)

    # Compute cosine similarity with all photos
    photo_ids = list(embeddings.keys())
    emb_matrix = np.stack([embeddings[pid] for pid in photo_ids])

    scores = emb_matrix @ query_vec  # cosine similarity (both normalized)

    # Sort by score descending
    top_indices = np.argsort(scores)[::-1][:limit]

    results = []
    for idx in top_indices:
        score = float(scores[idx])
        if score > 0.15:  # minimum relevance threshold
            results.append({
                "photo_id": photo_ids[idx],
                "score": round(score, 4),
            })

    return results


def get_search_stats():
    """Return cache statistics."""
    embeddings = _load_embeddings()
    return {
        "cached_embeddings": len(embeddings),
        "cache_age_seconds": int(time.time() - _cache_time) if _cache_time > 0 else None,
    }
