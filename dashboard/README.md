# Freerando Dashboard

Dashboard de monitoring pour le projet Freerando, tournant sur Raspberry Pi 5.

## Fonctionnalités

### Monitoring Système
- Temperature CPU (temps réel)
- Usage CPU global et par core
- Fréquence CPU
- Utilisation mémoire avec graphique historique
- Espace disque (barres de progression pour chaque partition)
- Réseau : adresses IP, vitesse upload/download

### Docker
- État du conteneur `icloudpd-shared` (running/stopped)
- Image et date de démarrage
- 20 dernières lignes de logs

### Sync iCloud Photos
- Nombre total de photos et espace utilisé
- Répartition par année (barres horizontales)
- Répartition par extension (HEIC, JPG, MOV...)
- 10 derniers fichiers téléchargés

### PostgreSQL
- Statut de connexion vers le serveur distant
- Taille de la base de données
- Version PostGIS
- Liste des tables et nombre de lignes

## Installation

```bash
chmod +x install.sh
./install.sh
```

Cela va :
1. Créer `/opt/freerando-dashboard/` et copier les fichiers
2. Créer un virtualenv Python et installer les dépendances
3. Installer et démarrer le service systemd

## Configuration

Éditer `config.py` ou créer un fichier `/opt/freerando-dashboard/.env` :

```env
PG_HOST=192.168.0.64
PG_PORT=5432
PG_DATABASE=freerando
PG_USER=freerando
PG_PASSWORD=freerando
```

## API Endpoints

| Endpoint | Description | Refresh |
|---|---|---|
| `GET /api/system` | Métriques système (CPU, RAM, disques, réseau) | 10s |
| `GET /api/docker` | État conteneur Docker + logs | 15s |
| `GET /api/photos` | Stats sync iCloud (compteurs, par année) | 5 min |
| `GET /api/postgres` | État PostgreSQL distant | 1 min |
| `GET /api/all` | Toutes les données combinées | - |

## Gestion du service

```bash
# Statut
sudo systemctl status freerando-dashboard

# Redémarrer
sudo systemctl restart freerando-dashboard

# Logs
sudo journalctl -u freerando-dashboard -f

# Désactiver
sudo systemctl disable freerando-dashboard
```

## Stack technique

- **Backend** : Flask + gunicorn (2 workers)
- **Frontend** : HTML/CSS/JS vanilla + Chart.js (CDN)
- **Pas de build step** : fichiers statiques servis directement
- **Dark theme** responsive (CSS Grid, 4 → 2 → 1 colonnes)

## Dépendances Python

- `flask` : serveur web
- `psutil` : métriques système
- `docker` : API Docker
- `psycopg2-binary` : client PostgreSQL
- `gunicorn` : serveur WSGI production
