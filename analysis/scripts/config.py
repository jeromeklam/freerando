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

# Traduction tags anglais → français
TAG_EN_TO_FR = {
    "mountain": "montagne", "lake": "lac", "forest": "forêt", "river": "rivière",
    "waterfall": "cascade", "valley": "vallée", "cliff": "falaise", "glacier": "glacier",
    "meadow": "prairie", "hill": "colline", "plateau": "plateau", "canyon": "canyon",
    "sunset": "coucher de soleil", "sunrise": "lever de soleil", "clouds": "nuages",
    "snow": "neige", "fog": "brouillard", "rain": "pluie", "blue sky": "ciel bleu",
    "night sky": "ciel étoilé",
    "flowers": "fleurs", "trees": "arbres", "rocks": "rochers", "path": "sentier",
    "trail": "sentier de randonnée",
    "dog": "chien", "cat": "chat", "bird": "oiseau", "cow": "vache", "horse": "cheval",
    "sheep": "mouton", "goat": "chèvre", "deer": "cerf", "chamois": "chamois",
    "marmot": "marmotte", "eagle": "aigle", "butterfly": "papillon", "bear": "ours",
    "elephant": "éléphant", "giraffe": "girafe", "zebra": "zèbre",
    "hiking": "randonnée", "skiing": "ski", "camping": "camping", "swimming": "natation",
    "cycling": "cyclisme",
    "person": "personne", "group of people": "groupe de personnes", "selfie": "selfie",
    "portrait": "portrait", "child": "enfant",
    "village": "village", "city": "ville", "church": "église", "castle": "château",
    "bridge": "pont", "refuge": "refuge", "cabin": "cabane",
    "food": "nourriture", "meal": "repas", "picnic": "pique-nique",
    "pizza": "pizza", "cake": "gâteau", "banana": "banane", "apple": "pomme",
    "orange": "orange", "carrot": "carotte", "broccoli": "brocoli",
    "beach": "plage", "sea": "mer", "boat": "bateau", "car": "voiture",
    "panorama": "panorama",
    "bicycle": "vélo", "motorcycle": "moto", "airplane": "avion", "bus": "bus",
    "train": "train", "truck": "camion",
    "traffic light": "feu de circulation", "fire hydrant": "bouche d'incendie",
    "stop sign": "panneau stop", "parking meter": "parcmètre",
    "bench": "banc", "backpack": "sac à dos", "umbrella": "parapluie",
    "handbag": "sac à main", "tie": "cravate", "suitcase": "valise",
    "frisbee": "frisbee", "skateboard": "skateboard", "surfboard": "planche de surf",
    "kite": "cerf-volant", "baseball glove": "gant de baseball",
    "sports ball": "ballon", "teddy bear": "ours en peluche",
    "chair": "chaise", "couch": "canapé", "bed": "lit", "dining table": "table",
    "toilet": "toilettes", "tv": "télévision", "laptop": "ordinateur portable",
    "keyboard": "clavier", "mouse": "souris", "remote": "télécommande",
    "cell phone": "téléphone", "microwave": "micro-ondes", "oven": "four",
    "refrigerator": "réfrigérateur", "sink": "évier", "clock": "horloge",
    "bottle": "bouteille", "wine glass": "verre à vin", "cup": "tasse",
    "fork": "fourchette", "knife": "couteau", "spoon": "cuillère",
    "bowl": "bol", "scissors": "ciseaux",
    "book": "livre", "vase": "vase", "potted plant": "plante en pot",
    "toothbrush": "brosse à dents",
}


def translate_tag(tag_en):
    """Translate an English tag to French."""
    return TAG_EN_TO_FR.get(tag_en.lower(), tag_en)
