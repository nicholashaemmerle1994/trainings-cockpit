#!/usr/bin/env bash
# Rollt den Freigabestand als Produktivinstanz auf dem Homeserver aus.
#
#   tools/deploy-main.sh             # main ausrollen und neu bauen
#   tools/deploy-main.sh <ref>       # einen anderen Stand ausrollen
#   tools/deploy-main.sh --no-build  # nur Dateien übertragen
#
# Gegenstück zu deploy-develop.sh: gleiche Mechanik, anderes Ziel. Ausgerollt
# wird der genannte Ref, NICHT der ausgecheckte Arbeitsbaum. data/ und .env
# liegen im Zielordner daneben und bleiben unangetastet.
set -euo pipefail

HOST="${TC_DEPLOY_HOST:-homeserver}"
REMOTE="${TC_DEPLOY_DIR:-\$HOME/docker/compose/cockpit}"
REF="main"
BUILD=1

for arg in "$@"; do
  case "$arg" in
    --no-build) BUILD=0 ;;
    -*) echo "Unbekannte Option: $arg" >&2; exit 2 ;;
    *) REF="$arg" ;;
  esac
done

cd "$(dirname "$0")/.."
git rev-parse --verify --quiet "$REF" >/dev/null || { echo "Ref '$REF' existiert nicht" >&2; exit 1; }
SHA="$(git rev-parse --short "$REF")"

echo "→ $REF ($SHA) nach $HOST:$REMOTE"
# Alte Dateien der ausgelieferten Bereiche entfernen, damit gelöschte Dateien
# nicht im Image zurückbleiben. data/ und .env liegen daneben und bleiben.
ssh "$HOST" "mkdir -p $REMOTE && cd $REMOTE && rm -rf src web tests tools docs"
git archive --format=tar "$REF" | ssh "$HOST" "tar xf - -C $REMOTE"

if [[ "$BUILD" == "1" ]]; then
  echo "→ Bauen und starten"
  ssh "$HOST" "cd $REMOTE && docker compose -p cockpit -f docker-compose.yml up -d --build --force-recreate"
  echo "→ Health (bis 45 s)"
  ssh "$HOST" 'for i in $(seq 1 15); do
    if curl -fsS -m 3 http://127.0.0.1:8100/api/health; then echo; exit 0; fi
    sleep 3
  done
  echo "Produktion antwortet nicht"; exit 1'
fi
