import os
from flask import Flask, jsonify, render_template, redirect, request, send_file, abort
from collectors import system, docker_status, icloud_sync, postgres_status, analysis_status
from services import photo_service, thumbnail_service, face_service, tag_service, album_service, clip_search_service
import config

app = Flask(__name__)


# --- Page routes ---
@app.route("/")
def index():
    return redirect("/dashboard")


@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html", active_tab="dashboard")


@app.route("/explorer")
def explorer():
    return render_template("explorer.html", active_tab="explorer")


@app.route("/faces")
def faces_page():
    return render_template("faces.html", active_tab="faces")


@app.route("/albums")
def albums_page():
    return render_template("albums.html", active_tab="albums")


# --- Monitoring API ---
@app.route("/api/system")
def api_system():
    return jsonify(system.collect())


@app.route("/api/docker")
def api_docker():
    return jsonify(docker_status.collect())


@app.route("/api/photos")
def api_photos():
    return jsonify(icloud_sync.collect())


@app.route("/api/postgres")
def api_postgres():
    return jsonify(postgres_status.collect())


@app.route("/api/analysis")
def api_analysis():
    return jsonify(analysis_status.collect())


@app.route("/api/all")
def api_all():
    return jsonify({
        "system": system.collect(),
        "docker": docker_status.collect(),
        "photos": icloud_sync.collect(),
        "postgres": postgres_status.collect(),
        "analysis": analysis_status.collect(),
    })


# --- Explorer API ---
@app.route("/api/explorer/photos")
def api_explorer_photos():
    photos, total = photo_service.search_photos(
        tag=request.args.get("tag"),
        source=request.args.get("source"),
        date_from=request.args.get("date_from"),
        date_to=request.args.get("date_to"),
        camera=request.args.get("camera"),
        face_id=request.args.get("face_id", type=int),
        q=request.args.get("q"),
        has_gps=request.args.get("has_gps", "0") == "1",
        sort=request.args.get("sort", "date_taken"),
        order=request.args.get("order", "desc"),
        page=request.args.get("page", 1, type=int),
        per_page=request.args.get("per_page", 50, type=int),
    )
    per_page = min(request.args.get("per_page", 50, type=int), 200)
    page = request.args.get("page", 1, type=int)
    return jsonify({
        "photos": photos,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page if per_page > 0 else 0,
    })


@app.route("/api/explorer/photo/<int:photo_id>")
def api_explorer_photo_detail(photo_id):
    photo = photo_service.get_photo_detail(photo_id)
    if not photo:
        abort(404)
    return jsonify(photo)


@app.route("/api/explorer/photo/<int:photo_id>/thumb")
def api_explorer_photo_thumb(photo_id):
    size = request.args.get("size", 300, type=int)
    if size not in (300, 1200):
        size = 300

    # Check cache first
    cached = thumbnail_service.get_thumbnail_path(photo_id, size)
    if cached:
        return send_file(cached, mimetype="image/jpeg")

    # Need filepath from DB
    photo = photo_service.get_photo_detail(photo_id)
    if not photo:
        abort(404)

    path = thumbnail_service.generate_thumbnail(photo["filepath"], photo_id, size)
    if not path:
        abort(404)
    return send_file(path, mimetype="image/jpeg")


@app.route("/api/explorer/photo/<int:photo_id>/full")
def api_explorer_photo_full(photo_id):
    photo = photo_service.get_photo_detail(photo_id)
    if not photo:
        abort(404)

    fullpath = os.path.join(config.PHOTOS_ROOT, photo["filepath"])
    if not os.path.exists(fullpath):
        abort(404)

    ext = photo.get("extension", "").lower()
    mimetypes = {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".png": "image/png", ".heic": "image/heic",
        ".gif": "image/gif",
    }
    return send_file(fullpath, mimetype=mimetypes.get(ext, "application/octet-stream"))


@app.route("/api/explorer/photos/geo")
def api_explorer_photos_geo():
    return jsonify(photo_service.get_geo_photos(
        tag=request.args.get("tag"),
        date_from=request.args.get("date_from"),
        date_to=request.args.get("date_to"),
    ))


@app.route("/api/explorer/filters")
def api_explorer_filters():
    return jsonify(photo_service.get_filters())


@app.route("/api/explorer/search/clip")
def api_clip_search():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"error": "q parameter required"}), 400
    limit = request.args.get("limit", 50, type=int)
    limit = min(limit, 200)
    results = clip_search_service.search_by_text(q, limit=limit)
    # Enrich with photo data
    if results:
        photo_ids = [r["photo_id"] for r in results]
        from services.db import db_cursor
        with db_cursor() as cur:
            cur.execute("""
                SELECT id, filename, filepath, date_taken, camera_model,
                       width, height, latitude, longitude
                FROM photos WHERE id = ANY(%s)
            """, (photo_ids,))
            photo_map = {}
            for row in cur.fetchall():
                p = {
                    "id": row[0], "filename": row[1], "filepath": row[2],
                    "date_taken": str(row[3]) if row[3] else None,
                    "camera_model": row[4],
                    "width": row[5], "height": row[6],
                    "latitude": float(row[7]) if row[7] else None,
                    "longitude": float(row[8]) if row[8] else None,
                    "thumb_url": f"/api/explorer/photo/{row[0]}/thumb",
                }
                photo_map[row[0]] = p

        enriched = []
        for r in results:
            photo = photo_map.get(r["photo_id"])
            if photo:
                photo["clip_score"] = r["score"]
                enriched.append(photo)
        return jsonify({"photos": enriched, "total": len(enriched), "query": q})

    return jsonify({"photos": [], "total": 0, "query": q})


# --- Tags API ---
@app.route("/api/tags/<int:tag_id>/confirm", methods=["PUT"])
def api_tag_confirm(tag_id):
    result = tag_service.confirm_tag(tag_id)
    if not result:
        abort(404)
    return jsonify(result)


@app.route("/api/tags/<int:tag_id>/label", methods=["PUT"])
def api_tag_label(tag_id):
    data = request.get_json()
    if not data:
        return jsonify({"ok": False, "error": "JSON body required"}), 400
    result = tag_service.update_tag_label(tag_id, data.get("label", "").strip())
    if not result:
        abort(404)
    return jsonify(result)


@app.route("/api/photos/<int:photo_id>/tags", methods=["POST"])
def api_add_tag(photo_id):
    data = request.get_json()
    if not data or not data.get("tag"):
        return jsonify({"ok": False, "error": "tag required"}), 400
    result = tag_service.add_manual_tag(
        photo_id, data["tag"].strip(),
        data.get("label", "").strip() or None,
        bbox=data.get("bbox"),
    )
    if not result.get("ok"):
        return jsonify(result), 409
    return jsonify(result), 201


@app.route("/api/tags/search")
def api_tag_search():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])
    return jsonify(tag_service.search_tags(q))


@app.route("/api/tags/<int:tag_id>", methods=["DELETE"])
def api_delete_tag(tag_id):
    result = tag_service.delete_tag(tag_id)
    if not result:
        abort(404)
    return jsonify(result)


# --- Faces API ---
@app.route("/api/faces")
def api_faces():
    return jsonify(face_service.list_faces(
        page=request.args.get("page", 1, type=int),
        per_page=request.args.get("per_page", 20, type=int),
    ))


@app.route("/api/faces/<int:face_id>/photos")
def api_face_photos(face_id):
    return jsonify(face_service.get_face_photos(
        face_id,
        page=request.args.get("page", 1, type=int),
        per_page=request.args.get("per_page", 50, type=int),
    ))


@app.route("/api/faces/<int:face_id>/crop")
def api_face_crop(face_id):
    info = face_service.get_face_crop_info(face_id)
    if not info:
        abort(404)

    # Check cache
    cached = thumbnail_service.get_face_crop_path(face_id)
    if cached:
        return send_file(cached, mimetype="image/jpeg")

    path = thumbnail_service.generate_face_crop(
        info["filepath"], face_id, info["photo_id"], info["bbox"]
    )
    if not path:
        abort(404)
    return send_file(path, mimetype="image/jpeg")


@app.route("/api/faces/<int:face_id>/label", methods=["PUT"])
def api_face_rename(face_id):
    data = request.get_json()
    if not data or not data.get("label"):
        return jsonify({"ok": False, "error": "label required"}), 400
    result = face_service.rename_face(face_id, data["label"].strip())
    if not result:
        abort(404)
    return jsonify(result)


@app.route("/api/faces/<int:face_id>/type", methods=["PUT"])
def api_face_type(face_id):
    data = request.get_json()
    if not data:
        return jsonify({"ok": False, "error": "JSON body required"}), 400
    result = face_service.update_face_type(face_id, data.get("face_type"))
    if not result:
        abort(404)
    return jsonify(result)


@app.route("/api/faces/merge", methods=["POST"])
def api_face_merge():
    data = request.get_json()
    if not data or not data.get("source_ids") or not data.get("target_id"):
        return jsonify({"ok": False, "error": "source_ids and target_id required"}), 400
    result = face_service.merge_faces(data["source_ids"], data["target_id"])
    return jsonify(result)


@app.route("/api/faces/search")
def api_face_search():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])
    return jsonify(face_service.search_faces(q))


@app.route("/api/faces", methods=["POST"])
def api_create_face():
    data = request.get_json()
    if not data or not data.get("label"):
        return jsonify({"ok": False, "error": "label required"}), 400
    result = face_service.create_face(data["label"].strip())
    return jsonify(result), 201


@app.route("/api/photos/<int:photo_id>/faces", methods=["POST"])
def api_add_face(photo_id):
    data = request.get_json()
    if not data or not data.get("face_id"):
        return jsonify({"ok": False, "error": "face_id required"}), 400
    bbox = data.get("bbox")
    result = face_service.assign_face_to_photo(photo_id, data["face_id"], bbox=bbox)
    if not result.get("ok"):
        return jsonify(result), 409
    return jsonify(result), 201


@app.route("/api/photos/<int:photo_id>/faces/<int:face_id>", methods=["DELETE"])
def api_remove_face(photo_id, face_id):
    result = face_service.remove_face_from_photo(photo_id, face_id)
    if not result:
        abort(404)
    return jsonify(result)


# --- Albums API ---
@app.route("/api/albums")
def api_albums():
    return jsonify(album_service.list_albums(
        page=request.args.get("page", 1, type=int),
        per_page=request.args.get("per_page", 20, type=int),
    ))


@app.route("/api/albums", methods=["POST"])
def api_create_album():
    data = request.get_json()
    if not data or not data.get("name"):
        return jsonify({"ok": False, "error": "name required"}), 400
    result = album_service.create_album(
        data["name"].strip(),
        data.get("description", "").strip() or None,
    )
    return jsonify(result), 201


@app.route("/api/albums/<int:album_id>")
def api_album_detail(album_id):
    album = album_service.get_album(album_id)
    if not album:
        abort(404)
    return jsonify(album)


@app.route("/api/albums/<int:album_id>", methods=["PUT"])
def api_update_album(album_id):
    data = request.get_json()
    if not data:
        return jsonify({"ok": False, "error": "JSON body required"}), 400
    result = album_service.update_album(
        album_id,
        name=data.get("name"),
        description=data.get("description"),
        cover_photo_id=data.get("cover_photo_id"),
    )
    if not result:
        abort(404)
    return jsonify(result)


@app.route("/api/albums/<int:album_id>", methods=["DELETE"])
def api_delete_album(album_id):
    result = album_service.delete_album(album_id)
    if not result:
        abort(404)
    return jsonify(result)


@app.route("/api/albums/<int:album_id>/photos")
def api_album_photos(album_id):
    return jsonify(album_service.get_album_photos(
        album_id,
        page=request.args.get("page", 1, type=int),
        per_page=request.args.get("per_page", 50, type=int),
    ))


@app.route("/api/albums/<int:album_id>/photos", methods=["POST"])
def api_add_album_photos(album_id):
    data = request.get_json()
    if not data or not data.get("photo_ids"):
        return jsonify({"ok": False, "error": "photo_ids required"}), 400
    result = album_service.add_photos_to_album(album_id, data["photo_ids"])
    if not result.get("ok"):
        return jsonify(result), 404
    return jsonify(result), 201


@app.route("/api/albums/<int:album_id>/photos/<int:photo_id>", methods=["DELETE"])
def api_remove_album_photo(album_id, photo_id):
    result = album_service.remove_photo_from_album(album_id, photo_id)
    if not result:
        abort(404)
    return jsonify(result)


@app.route("/api/photos/<int:photo_id>/albums")
def api_photo_albums(photo_id):
    return jsonify(album_service.get_photo_albums(photo_id))


if __name__ == "__main__":
    app.run(host=config.HOST, port=config.PORT, debug=config.DEBUG)
