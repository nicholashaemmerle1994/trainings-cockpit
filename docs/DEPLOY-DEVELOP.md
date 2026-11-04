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

Die Vorschau hängt nur im Tailnet, erreichbar über die Adresse des Servers:

```
http://100.92.2.97:8101
```

Bewusst **ohne** den `*.ts.net`-Namen und ohne HTTPS: dieser Name löst im
Browser nicht über MagicDNS, sondern über das öffentliche DNS auf die
Funnel-Ingress-Adresse auf — dort ist Port 8443 nicht offen, und der Browser
meldet `ERR_CONNECTION_CLOSED`. Die reine Tailnet-IP umgeht das.

Für „Zum Home-Bildschirm" auf dem iPhone reicht HTTP; die App hat keinen
Service Worker und braucht keinen sicheren Kontext.

Der Funnel für die Bibliothek (`/` → 8083) bleibt davon unberührt.

## Bauen und Starten

```bash
cd ~/docker/compose/cockpit-exp
TC_PORT=8101 docker compose -p cockpit-exp \
  -f docker-compose.yml -f docker-compose.develop.yml up -d --build
```

## Aktualisieren

Ein Befehl vom Arbeitsrechner aus, im Repository auf dem gewünschten Stand:

```bash
tools/deploy-develop.sh
```

Er überträgt die Dateien und baut neu. `--no-build` überträgt nur.

Was der Befehl tut: der Server hat keinen GitHub-Zugang, und `rsync` ist dort
nicht installiert.
Der Stand geht deshalb als Archiv über `ssh`:

```bash
# auf dem Mac, im Repository auf dem Stand von develop
COPYFILE_DISABLE=1 tar czf - \
  --exclude '.git' --exclude 'data' --exclude '.env' \
  --exclude '.venv' --exclude 'node_modules' --exclude 'web/node_modules' \
  --exclude 'web/dist' . \
| ssh homeserver 'tar xzf - -C ~/docker/compose/cockpit-exp'
```

Danach auf dem Server neu bauen (siehe oben). `data/`, `.env` und `.venv`
bleiben dabei unangetastet, weil sie nicht im Archiv liegen.

Wichtig ist `--force-recreate`: ohne das kann Compose einen laufenden Container
stehen lassen, obwohl ein neues Image gebaut wurde.

## Daten

`data/` ist eine Kopie der Produktivdaten, damit die Vorschau echte Zahlen
zeigt. Sie wird **nicht** automatisch nachgezogen; ein Sync in der Vorschau
schreibt nur in die Kopie. Die Produktivdatenbank bleibt unberührt.
