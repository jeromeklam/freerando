# Freerando

Synchronisation automatique de la photothèque iCloud partagée vers un Raspberry Pi 5, avec monitoring en temps réel et analyse d'images (en cours).

## Objectif

Ce projet fait partie du **Projet Randonnées** :
- Sync automatique de ~2 To de photos iCloud (bibliothèque partagée famille)
- Extraction des métadonnées EXIF (GPS, date, appareil) vers PostgreSQL/PostGIS
- Analyse d'images : tags sémantiques, reconnaissance de visages, détection animaux/objets
- Association automatique photos / randonnées via coordonnées GPS et dates

## Infrastructure

| Machine | Rôle | Specs |
|---|---|---|
| **yggdrasil** (Pi 5) | Stockage photos + analyse + dashboard | 8 Go RAM, NVMe 1.9 To |
| **dev** (Pi 5) | Base de données PostgreSQL/PostGIS | 8 Go RAM, NVMe 235 Go |

## Composants

### Sync iCloud (`icloudpd`)
- Container Docker `icloudpd-shared` avec sync hebdomadaire
- Photos stockées dans `/u01/photos/icloud-shared/{YYYY}/{MM}/{DD}/`
- Web UI sur le port 8080 pour la ré-authentification 2FA
- Mode archive : pas de suppression locale

### Dashboard Monitoring (`dashboard/`)
- Dashboard web Flask sur le port 8081
- Monitoring en temps réel : CPU, RAM, disques, réseau, température
- Suivi de la sync iCloud : nombre de photos, espace, progression
- État Docker et PostgreSQL
- Dark theme, responsive, graphiques Chart.js

### Analyse d'images (à venir)
- **CLIP** : tags sémantiques, recherche par texte libre
- **InsightFace** : clustering de visages
- **YOLO** : détection animaux et objets

## Installation

### Prérequis
- Raspberry Pi 5 avec Raspberry Pi OS Bookworm 64-bit
- Docker installé
- Python 3.11+

### Dashboard
```bash
cd dashboard
chmod +x install.sh
./install.sh
```
Le dashboard sera accessible sur `http://<IP_PI>:8081`.

## Structure du projet

```
freerando/
├── CLAUDE.md              # Instructions projet pour Claude Code
├── README.md              # Ce fichier
├── dashboard/             # Dashboard de monitoring
│   ├── app.py             # Application Flask
│   ├── config.py          # Configuration
│   ├── requirements.txt   # Dépendances Python
│   ├── install.sh         # Script d'installation
│   ├── freerando-dashboard.service  # Service systemd
│   ├── collectors/        # Modules de collecte de données
│   │   ├── system.py      # CPU, RAM, disques, réseau, température
│   │   ├── docker_status.py    # État conteneur Docker
│   │   ├── icloud_sync.py     # Progression sync iCloud
│   │   └── postgres_status.py  # État PostgreSQL distant
│   ├── static/
│   │   ├── css/style.css  # Dark theme responsive
│   │   └── js/
│   │       ├── dashboard.js  # Logique de rafraîchissement
│   │       └── charts.js     # Graphiques Chart.js
│   └── templates/
│       └── index.html     # Page unique du dashboard
└── .gitignore
```

## URLs

| Service | URL |
|---|---|
| Dashboard Freerando | http://192.168.0.66:8081 |
| Web UI icloudpd (2FA) | http://192.168.0.66:8080 |
| Dashboard PironMan5 | http://192.168.0.66:34001 |

## Licence

Projet personnel.
