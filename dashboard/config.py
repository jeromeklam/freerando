import os

# Flask
HOST = "0.0.0.0"
PORT = 8081
DEBUG = False

# Photo path
PHOTOS_ROOT = "/u01/photos/icloud-shared"

# Docker
DOCKER_CONTAINER_NAME = "icloudpd-shared"

# PostgreSQL (remote on dev)
PG_HOST = os.environ.get("PG_HOST", "192.168.0.64")
PG_PORT = int(os.environ.get("PG_PORT", "5432"))
PG_DATABASE = os.environ.get("PG_DATABASE", "freerando")
PG_USER = os.environ.get("PG_USER", "freerando")
PG_PASSWORD = os.environ.get("PG_PASSWORD", "freerando")

# Cache TTLs (seconds)
PHOTOS_CACHE_TTL = 300  # 5 minutes

# Thumbnails
THUMBNAIL_DIR = "/u01/photos/thumbnails"
