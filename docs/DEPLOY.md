# Deployment auf dem Homeserver

Das Cockpit läuft als Docker-Container, 24/7, mit lokaler SQLite-DB.
Keine Cloud, keine offenen Ports nach außen.

## Voraussetzungen

- Docker + Docker Compose auf dem Server (Linux, NAS oder Raspberry Pi)
- Dieses Projekt auf dem Server (git clone oder kopieren)
- `.env` mit den Keys (siehe `.env.example`)

## Start

```bash
cd trainings-cockpit
cp .env.example .env
chmod 600 .env
# Keys eintragen: INTERVALS_API_KEY, GARMIN_PERSONAL_API_KEY

TC_UID=$(id -u) TC_GID=$(id -g) docker compose up -d --build
```

Aufruf im LAN: `http://<server-ip>:8000`

Der Container läuft als dein Benutzer, damit er in `./data` schreiben darf.
Auf einem NAS ohne Shell-Benutzer kannst du `TC_UID`/`TC_GID` auch fest setzen
(z. B. `1000:1000`) und den Ordner `data/` entsprechend berechtigen.

## iPhone: App auf dem Home-Bildschirm

1. Seite in **Safari** öffnen (nicht Chrome).
2. Teilen-Symbol → **Zum Home-Bildschirm**.
3. Name „Cockpit" bestätigen.

Die Seite startet dann ohne Browser-Leiste. Für Installierbarkeit und
Service-Worker ist HTTPS empfehlenswert; im LAN funktioniert es auch über HTTP,
nur ohne Offline-Cache.

## HTTPS über Tailscale (empfohlen)

Wenn der Server in deinem Tailnet ist:

```bash
tailscale serve --bg 8000
```

Dann die angezeigte `https://…ts.net`-Adresse auf dem iPhone öffnen und
installieren. Kein Port im Internet, kein Zertifikat manuell.

## Daten und Backup

Alles liegt unter `./data`:

```
data/cockpit.db        SQLite-Datenbank
data/raw/              Rohdumps (intervals, Garmin, Push-Tests)
data/reports/          Phase-0-Befunde
```

### Automatisches Main-Backup auf dem Mac

Die Produktivdatenbank wird vom Homeserver über SSH auf diesen Mac geholt:

- **Datei:** `~/Backups/Trainings-Cockpit/main/cockpit-main.db`.
- **Zeitplan:** täglich 19:00 Uhr, zusätzlich Prüfung beim Anmelden und stündlich.
  Ein bereits abgedeckter Tageslauf wird ohne SSH-Übertragung übersprungen.
- **Ruhezustand:** macOS holt den Kalenderlauf beim Aufwachen nach. Nach dem
  Einschalten läuft die Prüfung beim Anmelden. Ist der Server nicht erreichbar,
  bleibt die Sicherung fällig und der nächste Stundenlauf versucht es erneut.
- **Aufbewahrung:** genau eine Datenbank. Die nächste geprüfte Sicherung ersetzt
  sie atomar; bei Übertragungs- oder Prüfungsfehlern bleibt die letzte erhalten.
- **Unabhängig von Codex:** ein macOS-LaunchAgent führt das Werkzeug aus.
  Develop wird nicht gesichert. Die Quelldatenbank wird nur gelesen.

Einrichtung oder Aktualisierung auf dem Mac:

```bash
/usr/bin/python3 tools/install-backup-agent.py
```

Das installiert eine eigene Werkzeugkopie unter
`~/Library/Application Support/Trainings-Cockpit/Backup/`; spätere Branchwechsel
oder das Schließen der App unterbrechen den Zeitplan nicht. Voraussetzung ist
ein eingerichteter, nichtinteraktiver `ssh homeserver`-Zugang und ein angemeldeter
Mac-Benutzer. Ist der Mac ausgeschaltet, kann er keine Sicherung holen.
Die Einrichtung übernimmt den vorhandenen SSH-Schlüssel als geschützte Kopie
in dieses Laufzeitverzeichnis, weil macOS Hintergrundzugriffe auf den ursprünglichen
Schlüssel im Dokumente-Ordner sperrt. Diese Datei bleibt lokal und wird nicht
versioniert. Die vorhandene Host-Key-Prüfung bleibt aktiv.

Status und Fehler stehen unter:

```text
~/Backups/Trainings-Cockpit/main/latest.json
~/Library/Logs/Trainings-Cockpit/backup.log
~/Library/Logs/Trainings-Cockpit/backup-error.log
```

Manuell eine neue Sicherung starten (ersetzt die letzte nach erfolgreicher Prüfung):

```bash
/usr/bin/python3 "$HOME/Library/Application Support/Trainings-Cockpit/Backup/backup-main.py" \
  --ssh-config "$HOME/Library/Application Support/Trainings-Cockpit/Backup/ssh-config"
launchctl print "gui/$(id -u)/com.nicholas.trainings-cockpit.backup"
```

Die Datei `cockpit-main.db` ist eine eigenständige SQLite-Datei und lässt sich
zum Beispiel mit DB Browser for SQLite öffnen. Zum Durchsehen eine separate
Kopie verwenden, damit die Sicherung unverändert bleibt.

**Wiederherstellung bei Serververlust:** Die gesicherte Datei zunächst auf eine
separate Arbeitskopie kopieren und mit SQLite `PRAGMA integrity_check` prüfen.
Auf dem Ersatzserver das Cockpit stoppen, eine eventuell vorhandene Datenbank
einschließlich ihrer WAL-/SHM-Dateien separat aufheben und die geprüfte Kopie als
`data/cockpit.db` einsetzen. Dateibesitzer und Rechte passend zum Container setzen,
dann starten und `/api/health` prüfen. Zugangsdaten aus `.env` und der Vault sind
nicht Bestandteil dieses Datenbank-Backups und müssen separat vorhanden sein.

**Einrichtung geprüft am 14.11.2026:** Der echte LaunchAgent-Lauf endete mit
Exit-Code 0. Ein zweiter Lauf ersetzte dieselbe Datei; Prüfsumme, SQLite-Integrität
und Wiederherstellung aus einer separaten Arbeitskopie wurden geprüft. Die sechs
Backup-Tests und Ruff sind erfolgreich. Die Gesamtsuite ergab 435 erfolgreiche
Tests und einen bereits auf unverändertem `main` reproduzierten Fehler:
`test_aktivitaetssync_zaehlt_neue_aufzeichnung_nur_einmal` vergleicht einen festen
November-Termin mit dem aktuellen rollierenden Sieben-Tage-Fenster.

### Zusätzliche Sicherung direkt auf dem Server

Für eine manuelle lokale Sicherung auf dem Server:

```bash
mkdir -p backup
sqlite3 data/cockpit.db ".backup 'backup/cockpit-$(date +%F).db'"
```

Die DB ist im WAL-Modus; für ein konsistentes Backup immer `.backup` verwenden,
nicht einfach die Datei kopieren.

## Update

```bash
git pull
TC_UID=$(id -u) TC_GID=$(id -g) docker compose up -d --build
```

## Betrieb prüfen

```bash
docker compose ps
docker compose logs -f cockpit
curl -s http://127.0.0.1:8000/api/health
```

## Sync

Aktuell wird per Knopf im Dashboard oder per CLI synchronisiert:

```bash
docker compose exec cockpit tc sync            # Rückstand seit dem letzten Lauf
docker compose exec cockpit tc sync --days 365 # volle Historie nachladen
```

Ohne `--days` liest der Sync nur, was seit dem letzten erfolgreichen Lauf neu
sein kann (mindestens einen Tag, nach einer Pause genau die Lücke). Der Knopf
im Dashboard tut dasselbe. Die volle Historie steht in der Datenbank und wird
nur bei Bedarf nachgeladen.

Ein automatischer Scheduler (morgens/abends) ist noch nicht eingebaut und
kommt in einer späteren Etappe.

## Release

`main` ist der Stand, der auf Port 8100 läuft. Freigegeben wird aus `develop`,
nachdem die Vorschau geprüft wurde: Knopf **Release** im Ticket-Board. Er merged
`develop` nach `main` (`--no-ff`), setzt den nächsten fortlaufenden Tag —
`v0.1.0` beim ersten Mal, danach `v0.2.0`, `v0.3.0` … —, pusht beides und rollt
die Produktion mit `tools/deploy-main.sh` aus. Danach zieht `develop` auf `main`
nach, damit die beiden Linien nicht auseinanderlaufen.

Von Hand ist es derselbe Weg:

```bash
git checkout develop && git pull --ff-only
git checkout main && git pull --ff-only
git merge --no-ff develop -m "Release v0.2.0"
git tag -a v0.2.0 -m "Release v0.2.0"
git push origin main --tags
git checkout develop && git merge --ff-only main && git push
tools/deploy-main.sh
```

**Die eine Regel:** `develop` ist immer in `main` enthalten. Hat `main` Commits,
die `develop` nicht kennt, verweigert der Release — dann erst `main` nach
`develop` mergen. Cherry-Picks sind weder für den Release noch für einen Hotfix
nötig:

- **Release:** `develop` → `main`, alles Getestete auf einmal.
- **Hotfix:** Branch von `main`, Fix, zurück nach `main`, danach `main` wieder
  nach `develop`.

Rückweg, wenn ein Release schlecht ist: `git revert` auf den Merge-Commit,
`tools/deploy-main.sh` erneut. Kein Force, keine verlorene Historie.
