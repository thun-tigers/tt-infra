# Operations

## Lokale Entwicklung

Voraussetzungen:

- Docker und Docker Compose
- lokale Checkouts von tt-auth, tt-members, tt-agenda, tt-analytics und tt-attendance neben diesem Repository

## Start

```bash
cp .env.example .env
docker compose -f docker-compose.yml -f docker-compose.local.yml up -d --build
```

## Erwartete Struktur

```text
tigers/
  tt-auth/
  tt-members/
  tt-agenda/
  tt-analytics/
  tt-attendance/
  tt-infra/
```

## Wichtige Hinweise

- Alle Services nutzen jeweils eigene Postgres-Datenbanken innerhalb eines gemeinsamen `tt-postgres`-Containers.
- tt-members, tt-analytics und tt-attendance sind fester Bestandteil des Standard-Stacks.
- JWT_COOKIE_DOMAIN muss je Umgebung korrekt gesetzt sein (Beta: .thun-tigers.net).
- Die zentrale Konfigurationsoberflaeche befindet sich in `tt-infra` unter `Admin -> Konfig` und gilt immer fuer die aktive Umgebung.

## Persistenz und Backups

Die Postgres-Daten liegen im gemeinsamen Docker-Volume `postgres-data` des Containers `tt-postgres`. Der Cluster enthaelt die Service-Datenbanken `tt_auth`, `tt_members`, `tt_agenda`, `tt_attendance`, `tt_analytics` und `tt_infra`.

Dadurch bleiben die Daten getrennt von den Applikationscontainern persistent. Fuer regelmaessige Backups sollte nicht das App-Dateisystem, sondern das Postgres-Volume bzw. ein `pg_dump`-Prozess pro Datenbank gesichert werden.

Empfohlener Weg:

- regelmaessige logische Dumps mit `pg_dump`
- zusaetzlich optional volumenbasierte Snapshots auf Host- oder Storage-Ebene
- Restore nicht in der App, sondern ueber `psql` oder `pg_restore`

## Deployment-Modi

### Lokale Direktnutzung

```bash
cp .env.example .env
docker compose -f docker-compose.yml -f docker-compose.local.yml up -d --build
```

### Beta-Umgebung auf Server

Voraussetzungen:

- fuer einen Blank-Server: nur `tt-infra` selbst muss vorhanden sein, die Fachservices werden als GHCR-Images gezogen
- `instance/platform-config.json` enthaelt die Secrets und wird vom Bootstrap oder der Config-UI erstellt
- `docker-compose.beta.yml` ist vorhanden

Start oder Update (siehe `docs/HANDOFF_CENTRAL_CONFIG_AND_PROXY.md`):

```bash
./setup.sh beta
```

Oder manuell:

```bash
./scripts/generate-env.sh beta
docker compose \
  --env-file ./instance/generated.env \
  -f docker-compose.beta.yml \
  up -d --build
```

Status pruefen:

```bash
docker compose \
  --env-file ./instance/generated.env \
  -f docker-compose.beta.yml \
  ps
```

### Arcane Beta mit Cloudflared Daemon

Fuer den Beta-Server mit Arcane und einem Cloudflared Daemon auf dem Host liegt eine eigene Anleitung bereit:

- `docs/beta-cloudflared-daemon.md`

Arcane ist dabei nur das Docker-Verwaltungswerkzeug und wird nicht oeffentlich geroutet. Der oeffentliche Einstieg ist `https://beta.thun-tigers.net`; Cloudflare Tunnel leitet die Domain pfad-basiert auf den Caddy-Reverse-Proxy (`tt-proxy`) im Stack.

### Produktion

Fuer Produktion liegt eine environment-basierte Konfiguration bereit:

- `.env.portainer.production.example` als Vorlage fuer Betriebsparameter und Secrets
- `releases/*.env` fuer den freigegebenen Satz an Service-Versionen
- Deployment erfolgt derzeit ebenfalls ueber `docker-compose.yml` in Verbindung mit `--env-file` (Secrets und Release-Manifest)

Empfohlenes Modell:

- Produktionsdeploys laufen ueber explizite Release-Tags wie `v1.0.0`
- Feste Image-Tags pro Service werden ueber ein Release-Manifest (`releases/X.Y.Z.env`) gepinnt
- Damit wird reproduzierbar und ohne implizite `latest`-Updates deployt

Empfohlene Trennung:

- Environment-Datei (aus `.env.portainer.production.example` abgeleitet) fuer Secrets und Betriebsparameter
- `releases/X.Y.Z.env` fuer den freigegebenen Satz an Service-Versionen

## CI/CD Image-Strategie

Die Repositories `tt-auth`, `tt-members`, `tt-agenda`, `tt-analytics`, `tt-attendance` und `tt-infra` enthalten standardisierte Container-Build-Workflows:

- Push auf `main`: baut `beta` und `sha-<commit>`
- Git-Tag `v*`: baut Release-Tag und `latest`
- `workflow_dispatch`: optionaler manueller Zusatz-Tag

Das ist absichtlich nicht auf jeden Branch ausgeweitet. Fuer Beta reicht in der Regel `main` als kontinuierlicher Integrationszweig. Produktion sollte ueber explizite Versionstags laufen.

## Versionierungsstandard

Verbindlicher Standard fuer alle Repositories:

- pro Repository gibt es genau eine massgebende Datei `VERSION`
- Inhalt von `VERSION` ist strikt `MAJOR.MINOR.PATCH`, zum Beispiel `0.1.0`
- Git-Release-Tags muessen exakt `v` plus `VERSION` entsprechen, zum Beispiel `v0.1.0`
- ein Tag `v0.1.0` ohne passende `VERSION` ist ungueltig und wird vom Workflow abgewiesen

Bedeutung:

- `MAJOR`: inkompatible Aenderungen
- `MINOR`: neue rueckwaerts-kompatible Funktionen
- `PATCH`: Bugfixes, Refactorings, kleine technische Korrekturen

Empfohlener Ablauf:

1. `VERSION` im betroffenen Repository erhoehen
2. Aenderungen auf `main` integrieren
3. Release-Tag `vX.Y.Z` auf den Commit setzen, der genau diese `VERSION` enthaelt
4. GitHub Actions baut das Release-Image und erstellt ein GitHub Release
5. Produktion zieht exakt diesen Tag in Portainer

## Release-Manifeste in tt-infra

Fuer freigegebene Plattform-Staende liegt in `tt-infra/releases` je Release eine eigene Manifest-Datei, aktuell z.B.:

- `releases/0.1.16.env`

Diese Dateien enthalten die Image-Tags pro Service, u.a.:

- `TT_INFRA_IMAGE_TAG`
- `TT_AUTH_IMAGE_TAG`
- `TT_MEMBERS_IMAGE_TAG`
- `TT_AGENDA_IMAGE_TAG`
- `TT_ANALYTICS_IMAGE_TAG`
- `TT_ATTENDANCE_IMAGE_TAG`

Beispiel fuer einen Produktions-Check (Env-Datei aus `.env.portainer.production.example` abgeleitet):

```bash
docker compose \
  --env-file .env.portainer.production \
  --env-file releases/0.1.16.env \
  -f docker-compose.yml \
  config
```

Beispiel fuer ein Deploy:

```bash
docker compose \
  --env-file .env.portainer.production \
  --env-file releases/0.1.16.env \
  -f docker-compose.yml \
  pull

docker compose \
  --env-file .env.portainer.production \
  --env-file releases/0.1.16.env \
  -f docker-compose.yml \
  up -d
```

Hinweis:

- Wenn das Deployment-Tool nur eine `.env`-Datei akzeptiert, koennen Secrets und Release-Manifest per `scripts/render_arcane_env.py` zu einer kombinierten Datei zusammengefuehrt werden.

## Release-Werkzeuge

`tt-infra` enthaelt zusaetzlich lokale Helfer fuer den Release-Vorlauf:

- `scripts/check_release_readiness.sh <version>`
- `scripts/tag_release.sh <version> --dry-run|--apply|--push`

Die Detailbeschreibung steht in `docs/releases.md`.

Konventionen fuer Commits:

- `feat: ...` fuer neue Funktionen
- `fix: ...` fuer Fehlerbehebungen
- `refactor: ...` fuer interne Umbauten ohne Funktionsaenderung
- `docs: ...` fuer reine Doku-Aenderungen
- `chore: ...` fuer Betriebs-, Build- oder Wartungsarbeiten

Faustregel fuer Versionsspruenge:

- nach `fix:` meistens `PATCH`
- nach `feat:` meistens `MINOR`
- bei API-, Datenmodell- oder Verhaltensbruch `MAJOR`

Bestandsnotiz:

- historische Alt-Tags, insbesondere in `tt-agenda`, bleiben bestehen
- ab diesem Standard ist die `VERSION`-Datei die einzige verbindliche Quelle fuer neue Releases

## Cloudflare Tunnel

- Cloudflare bleibt der externe Edge-Layer fuer DNS, TLS, WAF und Tunnel-Terminierung.
- Der Cloudflared Daemon leitet `beta.thun-tigers.net` pfad-basiert auf den Caddy-Reverse-Proxy (`tt-proxy`) im Stack (`http://host.docker.internal:80`).
- Details siehe `docs/HANDOFF_CENTRAL_CONFIG_AND_PROXY.md` und `docs/beta-cloudflared-daemon.md`.

## Bekannte Betriebsnotiz

Auf dem Server kann eine Docker-Warnung auftreten:

- Error loading config file: /root/.docker/config.json is a directory

Diese Warnung blockiert den Compose-Start nicht, sollte aber im Host-Setup bereinigt werden.
