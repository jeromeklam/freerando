from flask import Flask, jsonify, render_template
from collectors import system, docker_status, icloud_sync, postgres_status, analysis_status
import config

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html")


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


if __name__ == "__main__":
    app.run(host=config.HOST, port=config.PORT, debug=config.DEBUG)
