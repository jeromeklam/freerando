# Projet Freerando - Sync iCloud Photos & Analyse

## Contexte

Synchronisation automatique de la photothèque partagée iCloud (~2 To) vers un Raspberry Pi 5, avec extraction des métadonnées EXIF vers PostgreSQL/PostGIS et analyse d'images (CLIP, InsightFace, YOLO). Les photos serviront au "Projet Randonnées" : association automatique photos/randonnées via GPS + date, affichage sur carte Leaflet.

## Infrastructure

### yggdrasil — Raspberry Pi 5 (stockage + analyse)
- **OS** : Raspberry Pi OS Bookworm 64-bit (aarch64)
- **Hardware** : Pi 5 + PironMan5, 8 Go RAM, 4 cores Cortex-A76
- **NVMe système** : `/dev/nvme0n1` (238 Go) monté sur `/`
- **NVMe données** : `/dev/nvme1n1` (1.9 To) monté sur `/u01`
- **Docker** : 29.2.1
- **Photos** : `/u01/photos/icloud-shared/{YYYY}/{MM}/{DD}/`
- **User** : `jeromeklam` (uid=1002, groupes: www-data, sudo, docker)

### dev — Raspberry Pi 5 (base de données)
- **PostgreSQL** : 17, PostGIS 3.5
- **IP** : 192.168.0.64
- **Base** : `freerando` (user: `freerando`)

## Services actifs

| Service | Port | Description |
|---|---|---|
| icloudpd-shared (Docker) | 8080 | Sync iCloud + Web UI ré-auth 2FA |
| freerando-dashboard (systemd) | 8081 | Dashboard monitoring |
| PironMan5 | 34001 | Dashboard hardware Pi |

## Architecture

```
yggdrasil (Pi5)                         dev (Pi5)
┌──────────────────────────────┐       ┌──────────────────┐
│ Docker                       │       │ PostgreSQL 17    │
│  └─ icloudpd-shared (:8080) │       │  └─ PostGIS 3.5  │
│     └─ /u01/photos/icloud-shared/    │  └─ DB freerando │
│                              │       └──────────────────┘
│ Dashboard Flask (:8081)      │              ▲
│  └─ /opt/freerando-dashboard/│              │
│                              │       résultats (tags,
│ Analyse (à venir)            │       GPS, faces...)
│  ├─ CLIP (tags sémantiques)  │──────────────┘
│  ├─ InsightFace (visages)    │
│  └─ YOLO (objets/animaux)   │
└──────────────────────────────┘
```

## Décisions techniques

### Sync iCloud
- **Outil** : icloudpd officiel en Docker (`icloudpd/icloudpd:latest`)
- **Bibliothèque** : `SharedSync-6AA3A8E0-7DBA-4090-A051-1F0E65AA080A`
- **Organisation** : `{:%Y/%m/%d}` (année/mois/jour)
- **Mode** : Archive (jamais de suppression locale, pas de `--auto-delete`)
- **Fréquence** : Hebdomadaire (`--watch-with-interval 604800`)
- **EXIF** : `--set-exif-datetime` activé
- **Taille** : Originaux (`--size original`)
- **MFA** : Web UI intégrée sur port 8080 (`--mfa-provider webui`)
- **Timezone** : Europe/Paris

### Dashboard
- **Backend** : Flask + gunicorn (2 workers)
- **Frontend** : Vanilla HTML/CSS/JS + Chart.js
- **Installé** : `/opt/freerando-dashboard/`
- **Source** : `dashboard/` dans ce repo
- **Service** : `freerando-dashboard.service` (systemd)

### Analyse d'images (à venir)
- **CLIP** : tags sémantiques, recherche par texte libre
- **InsightFace** : détection et clustering de visages
- **YOLO** : détection objets/animaux
- **Stockage** : résultats dans PostgreSQL/PostGIS sur dev

## Commandes utiles

```bash
# Sync iCloud
docker logs -f icloudpd-shared
docker restart icloudpd-shared

# Dashboard
sudo systemctl status freerando-dashboard
sudo systemctl restart freerando-dashboard

# Photos
du -sh /u01/photos/icloud-shared/
find /u01/photos/icloud-shared/ -type f | wc -l
exiftool FICHIER.HEIC | grep -i "gps\|date\|model"

# PostgreSQL (depuis yggdrasil)
PGPASSWORD=freerando psql -h dev -U freerando -d freerando
```

## Points d'attention

- Le cookie 2FA expire tous les ~2 mois → ré-auth via http://192.168.0.66:8080
- Apple peut rate-limiter les gros downloads → ne pas relancer en boucle si erreur
- Advanced Data Protection DOIT être désactivé sinon ACCESS_DENIED
- Pas de `--auto-delete` : on est en mode archive
- Sudo sans mot de passe configuré sur les deux Pi : `/etc/sudoers.d/jeromeklam`
