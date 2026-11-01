#!/bin/bash
# Zieht neue Daten: intervals.icu → Cockpit-Datenbank → Sport-Gehirn.
# Läuft per launchd jeden Morgen, ohne dass etwas geöffnet sein muss.
set -uo pipefail

COCKPIT="$HOME/Documents/deepseek-harness/default-workspace/trainings-cockpit"
VAULT="$HOME/Documents/Sport-Gehirn"
UV="$HOME/.local/bin/uv"
LOG="$COCKPIT/data/logs/sync.log"

mkdir -p "$(dirname "$LOG")"
{
  echo "=== $(date '+%Y-%m-%d %H:%M:%S') Start ==="
  cd "$COCKPIT" || { echo "Cockpit-Ordner fehlt"; exit 1; }

  export UV_CACHE_DIR="$COCKPIT/.uv-cache"
  export UV_PYTHON_INSTALL_DIR="$COCKPIT/.uv-python"

  # 14 Tage zurück: fängt neue Einheiten und nachträgliche Korrekturen.
  # Drei Versuche, weil intervals.icu gelegentlich den TLS-Handshake abbricht.
  ok=0
  for versuch in 1 2 3; do
    if "$UV" run tc sync --days 14; then ok=1; break; fi
    echo "Versuch $versuch fehlgeschlagen, 60 s Pause"
    sleep 60
  done
  [ "$ok" = 1 ] || echo "WARNUNG: sync nach drei Versuchen fehlgeschlagen"

  if [ -d "$VAULT" ]; then
    "$UV" run python tools/vault_import.py --vault "$VAULT" || echo "WARNUNG: Import fehlgeschlagen"
    ( cd "$VAULT" && /usr/bin/python3 _system/skripte/aktualisieren.py ) || echo "WARNUNG: Skript fehlgeschlagen"
  else
    echo "WARNUNG: Vault nicht gefunden ($VAULT)"
  fi

  echo "=== $(date '+%Y-%m-%d %H:%M:%S') Ende ==="
} >> "$LOG" 2>&1
