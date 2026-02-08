import os

PHOTOS_ROOT = "/u01/photos/icloud-shared"

PG_HOST = os.environ.get("PG_HOST", "192.168.0.64")
PG_PORT = int(os.environ.get("PG_PORT", "5432"))
PG_DATABASE = os.environ.get("PG_DATABASE", "freerando")
PG_USER = os.environ.get("PG_USER", "freerando")
PG_PASSWORD = os.environ.get("PG_PASSWORD", "freerando")

# CLIP settings
CLIP_MODEL = "ViT-B-32"
CLIP_PRETRAINED = "laion2b_s34b_b79k"
CLIP_TAGS = [
    # Landscapes
    "mountain", "lake", "forest", "river", "waterfall", "valley",
    "cliff", "glacier", "meadow", "hill", "plateau", "canyon",
    # Weather/sky
    "sunset", "sunrise", "clouds", "snow", "fog", "rain", "blue sky",
    # Nature
    "flowers", "trees", "rocks", "path", "trail",
    # Animals
    "dog", "cat", "bird", "cow", "horse", "sheep", "goat",
    "deer", "chamois", "marmot", "eagle", "butterfly",
    # Activity
    "hiking", "skiing", "camping", "swimming", "cycling",
    # People
    "person", "group of people", "selfie", "portrait", "child",
    # Places
    "village", "city", "church", "castle", "bridge", "refuge", "cabin",
    # Food
    "food", "meal", "picnic",
    # Other
    "beach", "sea", "boat", "car", "panorama", "night sky",
]
CLIP_THRESHOLD = 0.20  # minimum similarity score to keep a tag

# YOLO settings
YOLO_MODEL = "yolo11n.pt"
YOLO_CONFIDENCE = 0.40

# InsightFace settings
INSIGHTFACE_MODEL = "buffalo_l"
INSIGHTFACE_DET_SIZE = (640, 640)
FACE_SIMILARITY_THRESHOLD = 0.45  # for clustering
