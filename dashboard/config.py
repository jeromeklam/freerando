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

# Traduction tags anglais → français (CLIP + YOLO)
TAG_EN_TO_FR = {
    # Paysages
    "mountain": "montagne", "lake": "lac", "forest": "forêt", "river": "rivière",
    "waterfall": "cascade", "valley": "vallée", "cliff": "falaise", "glacier": "glacier",
    "meadow": "prairie", "hill": "colline", "plateau": "plateau", "canyon": "canyon",
    # Météo / ciel
    "sunset": "coucher de soleil", "sunrise": "lever de soleil", "clouds": "nuages",
    "snow": "neige", "fog": "brouillard", "rain": "pluie", "blue sky": "ciel bleu",
    "night sky": "ciel étoilé",
    # Nature
    "flowers": "fleurs", "trees": "arbres", "rocks": "rochers", "path": "sentier",
    "trail": "sentier de randonnée",
    # Animaux
    "dog": "chien", "cat": "chat", "bird": "oiseau", "cow": "vache", "horse": "cheval",
    "sheep": "mouton", "goat": "chèvre", "deer": "cerf", "chamois": "chamois",
    "marmot": "marmotte", "eagle": "aigle", "butterfly": "papillon", "bear": "ours",
    "elephant": "éléphant", "giraffe": "girafe", "zebra": "zèbre",
    # Activités
    "hiking": "randonnée", "skiing": "ski", "camping": "camping", "swimming": "natation",
    "cycling": "cyclisme",
    # Personnes
    "person": "personne", "group of people": "groupe de personnes", "selfie": "selfie",
    "portrait": "portrait", "child": "enfant",
    # Lieux
    "village": "village", "city": "ville", "church": "église", "castle": "château",
    "bridge": "pont", "refuge": "refuge", "cabin": "cabane",
    # Nourriture
    "food": "nourriture", "meal": "repas", "picnic": "pique-nique",
    "pizza": "pizza", "cake": "gâteau", "banana": "banane", "apple": "pomme",
    "orange": "orange", "carrot": "carotte", "broccoli": "brocoli",
    # Autre
    "beach": "plage", "sea": "mer", "boat": "bateau", "car": "voiture",
    "panorama": "panorama",
    # YOLO objets courants
    "bicycle": "vélo", "motorcycle": "moto", "airplane": "avion", "bus": "bus",
    "train": "train", "truck": "camion", "traffic light": "feu de circulation",
    "fire hydrant": "bouche d'incendie", "stop sign": "panneau stop",
    "parking meter": "parcmètre", "bench": "banc", "backpack": "sac à dos",
    "umbrella": "parapluie", "handbag": "sac à main", "tie": "cravate",
    "suitcase": "valise", "frisbee": "frisbee", "skateboard": "skateboard",
    "surfboard": "planche de surf", "kite": "cerf-volant",
    "baseball glove": "gant de baseball", "sports ball": "ballon",
    "teddy bear": "ours en peluche",
    # YOLO intérieur
    "chair": "chaise", "couch": "canapé", "bed": "lit", "dining table": "table",
    "toilet": "toilettes", "tv": "télévision", "laptop": "ordinateur portable",
    "keyboard": "clavier", "mouse": "souris", "remote": "télécommande",
    "cell phone": "téléphone", "microwave": "micro-ondes", "oven": "four",
    "refrigerator": "réfrigérateur", "sink": "évier", "clock": "horloge",
    # YOLO ustensiles
    "bottle": "bouteille", "wine glass": "verre à vin", "cup": "tasse",
    "fork": "fourchette", "knife": "couteau", "spoon": "cuillère",
    "bowl": "bol", "scissors": "ciseaux",
    # YOLO autre
    "book": "livre", "vase": "vase", "potted plant": "plante en pot",
    "toothbrush": "brosse à dents",
}

# Thumbnails
THUMBNAIL_DIR = "/u01/photos/thumbnails"
