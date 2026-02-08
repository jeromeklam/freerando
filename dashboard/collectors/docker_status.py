import docker
import config

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = docker.from_env()
    return _client


def collect():
    try:
        client = _get_client()
        container = client.containers.get(config.DOCKER_CONTAINER_NAME)

        status = container.status
        started_at = container.attrs["State"].get("StartedAt", "")

        logs = container.logs(tail=20, timestamps=True).decode("utf-8", errors="replace")
        log_lines = logs.strip().split("\n") if logs.strip() else []

        return {
            "container_name": config.DOCKER_CONTAINER_NAME,
            "status": status,
            "started_at": started_at,
            "image": container.image.tags[0] if container.image.tags else "unknown",
            "logs": log_lines[-20:],
            "error": None,
        }
    except docker.errors.NotFound:
        return {
            "container_name": config.DOCKER_CONTAINER_NAME,
            "status": "not_found",
            "started_at": None,
            "image": None,
            "logs": [],
            "error": f"Container '{config.DOCKER_CONTAINER_NAME}' not found",
        }
    except Exception as e:
        global _client
        _client = None
        return {
            "container_name": config.DOCKER_CONTAINER_NAME,
            "status": "error",
            "started_at": None,
            "image": None,
            "logs": [],
            "error": str(e),
        }
