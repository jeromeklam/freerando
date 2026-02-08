import os
from flask import Flask, jsonify, render_template, redirect, request, send_file, abort
from collectors import system, docker_status, icloud_sync, postgres_status, analysis_status
from services import photo_service, thumbnail_service, face_service
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


@app.route("/api/faces/merge", methods=["POST"])
def api_face_merge():
    data = request.get_json()
    if not data or not data.get("source_ids") or not data.get("target_id"):
        return jsonify({"ok": False, "error": "source_ids and target_id required"}), 400
    result = face_service.merge_faces(data["source_ids"], data["target_id"])
    return jsonify(result)


if __name__ == "__main__":
    app.run(host=config.HOST, port=config.PORT, debug=config.DEBUG)
