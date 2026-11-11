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
| Port | 8100 | 8101 und zusätzlich 8081 |
| Datenbank | `data/cockpit.db` | eigene Kopie in `data/` |

## Erreichbarkeit

Die Vorschau hängt nur im Tailnet, erreichbar über die Adresse des Servers:

```
http://100.92.2.97:8101

Zusätzlich ist dieselbe Vorschau unter `http://100.92.2.97:8081` erreichbar.
```

Bewusst **ohne** den `*.ts.net`-Namen und ohne HTTPS: dieser Name löst im
Browser nicht über MagicDNS, sondern über das öffentliche DNS auf die
Funnel-Ingress-Adresse auf — dort ist Port 8443 nicht offen, und der Browser
meldet `ERR_CONNECTION_CLOSED`. Die reine Tailnet-IP umgeht das.

Für „Zum Home-Bildschirm" auf dem iPhone reicht HTTP; die App hat keinen
Service Worker und braucht keinen sicheren Kontext.

Der Funnel für die Bibliothek (`/` → 8083) bleibt davon unberührt.

## Erkennungszeichen

Der Vorschau-Bau setzt `VITE_APP_VARIANT=preview` (steht als Build-Argument in
`docker-compose.develop.yml`). Damit trägt die App einen offenen Akzent-Ring, die
Plakette „Vorschau", den Titel „Trainings-Cockpit · Vorschau" und ein eigenes
Startbildschirm-Icon („Cockpit Vorschau"). Der stabile Bau bleibt unverändert;
ohne den Wert entsteht wieder das normale Logo.

## Bauen und Starten

```bash
cd ~/docker/compose/cockpit-exp
TC_PORT=8101 docker compose -p cockpit-exp \
  -f docker-compose.yml -f docker-compose.develop.yml up -d --build
```

## Aktualisieren

Ein Befehl vom Arbeitsrechner aus:

```bash
tools/deploy-develop.sh          # develop ausrollen
tools/deploy-develop.sh main     # anderen Stand ausrollen
```

Ausgerollt wird ein **Branch aus dem Repository**, nicht der ausgecheckte
Arbeitsbaum. Das ist Absicht: während ein Ticket-Agent auf seinem
Feature-Branch arbeitet, darf dessen Zwischenstand nicht auf dem Server
landen. Das Skript nimmt `git archive`, überträgt per `ssh` und baut neu.
`--no-build` überträgt nur.

Die Vorschau wird über `TC_PORT` (Standard 8101) und zusätzlich über
`TC_ALT_PORT` (Standard 8081) veröffentlicht. Beide zeigen dieselbe Instanz.

Danach auf dem Server neu bauen (siehe oben). `data/`, `.env` und `.venv`
bleiben dabei unangetastet, weil sie nicht im Archiv liegen.

Wichtig ist `--force-recreate`: ohne das kann Compose einen laufenden Container
stehen lassen, obwohl ein neues Image gebaut wurde.

## Daten

`data/` ist eine Kopie der Produktivdaten, damit die Vorschau echte Zahlen
zeigt. Sie wird **nicht** automatisch nachgezogen; ein Sync in der Vorschau
schreibt nur in die Kopie. Die Produktivdatenbank bleibt unberührt.
