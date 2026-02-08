#!/bin/bash
set -euo pipefail

INSTALL_DIR="/opt/freerando-dashboard"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== Freerando Dashboard Installer ==="

# Create directory
sudo mkdir -p "$INSTALL_DIR"
sudo chown "$USER:www-data" "$INSTALL_DIR"

# Copy files
cp -r "$SCRIPT_DIR"/{app.py,config.py,requirements.txt,collectors,static,templates} "$INSTALL_DIR/"

# Create venv and install deps
if [ ! -d "$INSTALL_DIR/venv" ]; then
    python3 -m venv "$INSTALL_DIR/venv"
fi
"$INSTALL_DIR/venv/bin/pip" install --upgrade pip -q
"$INSTALL_DIR/venv/bin/pip" install -r "$INSTALL_DIR/requirements.txt" -q

# Install systemd service
sudo cp "$SCRIPT_DIR/freerando-dashboard.service" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable freerando-dashboard
sudo systemctl restart freerando-dashboard

IP=$(hostname -I | awk '{print $1}')
echo "=== Dashboard disponible sur http://${IP}:8081 ==="
