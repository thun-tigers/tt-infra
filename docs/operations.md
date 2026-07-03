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

- tt-auth, tt-agenda, tt-attendance und tt-analytics nutzen jeweils eigene Postgres-Datenbanken.
- tt-members, tt-analytics und tt-attendance sind fester Bestandteil des Standard-Stacks.
- JWT_COOKIE_DOMAIN muss je Umgebung korrekt gesetzt sein (Beta: .thun-tigers.net).

## Persistenz und Backups

Die Datenbanken laufen in eigenen Docker-Volumes:

- `postgres-auth-data`
- `postgres-agenda-data`
- `postgres-attendance-data`
- `postgres-analytics-data`

Dadurch bleiben die Daten getrennt von den Applikationscontainern persistent. Fuer regelmaessige Backups sollte nicht das App-Dateisystem, sondern das jeweilige Postgres-Volume bzw. ein `pg_dump`-Prozess gesichert werden.

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

- .env.beta ist vorhanden
- docker-compose.beta.yml ist vorhanden
- Quellcode der Services liegt auf dem Server in benachbarten Verzeichnissen

Start oder Update:

```bash
docker compose --env-file .env.beta \
  -f docker-compose.yml \
  -f docker-compose.local.yml \
  -f docker-compose.beta.yml \
  up -d --build
```

Status pruefen:

```bash
docker compose --env-file .env.beta \
  -f docker-compose.yml \
  -f docker-compose.local.yml \
  -f docker-compose.beta.yml \
  ps
```

### Portainer Beta

Fuer einen image-basierten Stack in Portainer liegt eine eigenstaendige Compose-Datei bereit:

- `docker-compose.portainer.beta.yml`
- `.env.portainer.beta.example`

Empfohlenes Modell:

- `main` baut automatisch GHCR-Images mit dem Tag `beta`
- Portainer zieht fuer Beta immer die `beta`-Tags
- Deploy der Stack-Datei direkt aus dem Git-Repository oder per Copy/Paste in Portainer

### Arcane Beta mit Cloudflared Daemon

Fuer den neuen Beta-Server mit Arcane und einem Cloudflared Daemon auf dem Host liegt eine eigene Anleitung bereit:

- `docs/beta-cloudflared-daemon.md`

Arcane ist dabei nur das Docker-Verwaltungswerkzeug und wird nicht oeffentlich geroutet. Der oeffentliche Einstieg ist `https://beta.thun-tigers.net`; Cloudflare Tunnel leitet die Beta-Domains auf die lokalen `608x`-Ports der Services.

### Portainer Produktion

Fuer Produktion liegt ebenfalls eine image-basierte Compose-Datei bereit:

- `docker-compose.portainer.production.yml`
- `.env.portainer.production.example`
- `releases/*.env`

Empfohlenes Modell:

- Produktionsdeploys laufen ueber explizite Release-Tags wie `v1.0.0`
- Die Production-Compose erwartet bewusst feste Image-Tags pro Service
- Portainer deployt damit reproduzierbar und ohne implizite `latest`-Updates

Empfohlene Trennung:

- `.env.production` oder Portainer-Umgebungsvariablen fuer Secrets und Betriebsparameter
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

Fuer freigegebene Plattform-Staende liegt in `tt-infra/releases` je Release eine eigene Manifest-Datei:

- `releases/0.1.0.env`

Diese Dateien enthalten nur:

- `TT_INFRA_IMAGE_TAG`
- `TT_AUTH_IMAGE_TAG`
- `TT_MEMBERS_IMAGE_TAG`
- `TT_AGENDA_IMAGE_TAG`
- `TT_ANALYTICS_IMAGE_TAG`

Beispiel fuer einen Produktions-Check:

```bash
docker compose \
  --env-file .env.production \
  --env-file releases/0.1.0.env \
  -f docker-compose.portainer.production.yml \
  config
```

Beispiel fuer ein Deploy:

```bash
docker compose \
  --env-file .env.production \
  --env-file releases/0.1.0.env \
  -f docker-compose.portainer.production.yml \
  pull

docker compose \
  --env-file .env.production \
  --env-file releases/0.1.0.env \
  -f docker-compose.portainer.production.yml \
  up -d
```

Portainer-Hinweis:

- wenn Portainer keine zwei `.env`-Dateien elegant kombiniert, bleiben die Secrets in Portainer
- die fuenf `TT_*_IMAGE_TAG` Werte werden dann aus dem gewuenschten Release-Manifest manuell uebernommen

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
- Der Cloudflared Daemon auf dem Server leitet die Beta-Hostnames auf die lokalen `608x`-Ports der Services.
- Pfadbasiertes Routing wurde bewusst nicht als Standardmodell gewaehlt, weil die bestehenden Apps sauberer ueber eigene Subdomains betrieben werden koennen.

## Bekannte Betriebsnotiz

Auf dem Server kann eine Docker-Warnung auftreten:

- Error loading config file: /root/.docker/config.json is a directory

Diese Warnung blockiert den Compose-Start nicht, sollte aber im Host-Setup bereinigt werden.
