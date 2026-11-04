#!/usr/bin/env bash
# Rollt den aktuellen Stand als Vorschau-Instanz auf den Homeserver aus.
#
#   tools/deploy-develop.sh            # ausrollen und neu bauen
#   tools/deploy-develop.sh --no-build # nur Dateien übertragen
#
# Erwartet den ssh-Host `homeserver` (siehe ~/.ssh/config) und ein
# Repository auf dem Stand, der ausgerollt werden soll.
set -euo pipefail

HOST="${TC_DEPLOY_HOST:-homeserver}"
REMOTE="${TC_DEPLOY_DIR:-\$HOME/docker/compose/cockpit-exp}"
BUILD=1
[[ "${1:-}" == "--no-build" ]] && BUILD=0

cd "$(dirname "$0")/.."

echo "→ Dateien nach $HOST:$REMOTE"
COPYFILE_DISABLE=1 tar czf - \
  --exclude '.git' --exclude 'data' --exclude '.env' \
  --exclude '.venv' --exclude 'node_modules' --exclude 'web/node_modules' \
  --exclude 'web/dist' --exclude '.DS_Store' --exclude '__pycache__' \
  --exclude '.pytest_cache' --exclude '.ruff_cache' . \
  | ssh "$HOST" "tar xzf - -C $REMOTE"

if [[ "$BUILD" == "1" ]]; then
  echo "→ Bauen und starten"
  ssh "$HOST" "cd $REMOTE && TC_PORT=8101 docker compose -p cockpit-exp \
    -f docker-compose.yml -f docker-compose.develop.yml up -d --build --force-recreate"
  echo "→ Health"
  ssh "$HOST" "curl -sS -m 5 http://127.0.0.1:8101/api/health"
  echo
fi
