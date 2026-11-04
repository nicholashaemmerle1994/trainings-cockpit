# Vorschau-Instanz (develop)

Auf dem Homeserver läuft neben dem Cockpit auf Port 8100 eine zweite Instanz
derselben App, gebaut aus dem Stand von `develop`. Sie ist zum Ansehen und
Ausprobieren: das, was ein Ticket gebaut hat, soll dort landen, bevor es nach
`main` kommt.

| | Cockpit (main) | Vorschau (develop) |
|---|---|---|
| Verzeichnis | `~/docker/compose/cockpit` | `~/docker/compose/cockpit-exp` |
| Compose-Projekt | `cockpit` | `cockpit-exp` |
| Image | `trainings-cockpit:latest` | `trainings-cockpit:develop` |
| Port | 8100 | 8101 |
| Datenbank | `data/cockpit.db` | eigene Kopie in `data/` |

## Erreichbarkeit

Die Vorschau hängt am Tailnet, nicht im Internet:

```bash
tailscale serve --bg --https=8443 http://127.0.0.1:8101
```

Aufruf danach: `https://<hostname>.<tailnet>.ts.net:8443`. Über HTTPS lässt
sich die Seite auf dem iPhone über „Zum Home-Bildschirm" als App ablegen
(Manifest und Icons liegen in `web/public/`).

## Bauen und Starten

```bash
cd ~/docker/compose/cockpit-exp
TC_PORT=8101 docker compose -p cockpit-exp \
  -f docker-compose.yml -f docker-compose.develop.yml up -d --build
```

## Aktualisieren

Der Stand kommt per `rsync` vom Arbeitsrechner (der Server hat keinen
GitHub-Zugang):

```bash
# auf dem Mac, aus dem Repository
rsync -az --delete \
  --exclude '.git' --exclude 'data' --exclude '.env' \
  --exclude '.venv' --exclude 'node_modules' --exclude 'web/node_modules' \
  ./ homeserver:~/docker/compose/cockpit-exp/
```

Danach auf dem Server neu bauen (siehe oben).

## Daten

`data/` ist eine Kopie der Produktivdaten, damit die Vorschau echte Zahlen
zeigt. Sie wird **nicht** automatisch nachgezogen; ein Sync in der Vorschau
schreibt nur in die Kopie. Die Produktivdatenbank bleibt unberührt.
