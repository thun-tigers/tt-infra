# tt-infra

Infrastruktur-, Operations- und Plattform-Repository fuer den Tigers-Microservice-Stack.

## Zweck

Dieses Repository enthaelt die zentrale Infrastruktur fuer:

- Docker Compose Stack
- Umgebungsvariablen
- Betriebsdokumentation
- Architekturuebersichten
- Deployment-Vorbereitung

Die fachlichen Anwendungen bleiben in separaten Repositories:

- `tt-auth`
- `tt-members`
- `tt-agenda`
- `tt-analytics`
- `tt-attendance`

## Zielbild

tt-auth ist der zentrale Identity- und Access-Service.
tt-infra betreibt den Compose-Stack, Netzwerk, Umgebungen und Betriebsprozesse.
Fachliche Anwendungen wie tt-members, tt-agenda, tt-analytics und tt-attendance laufen als eigene Services.

## Struktur

- docker-compose.yml zentraler Compose-Stack
- docker-compose.local.yml lokale Port-Freigaben fuer Entwicklung
- docker-compose.arcane.beta.yml Beta-Stack fuer Arcane plus Cloudflared Daemon
- platform_config.py zentrale Quelle fuer die Platform-Profile
- app/routes/config.py Konfigurationsoberflaeche fuer die aktuelle Umgebung und Exporte
- app/templates/config/ UI fuer die laufende Umgebung
- scripts/render_platform_env.py Generator fuer `.env`-Dateien und Release-Manifeste
- .env.arcane.beta aus der zentralen Konfiguration gerendert
- .env.example aus der zentralen Konfiguration gerendert
- docs/architecture.md Zielarchitektur und Standards
- docs/stack-architecture.md detaillierte Plattform-Architektur
- docs/operations.md Betriebs- und Deployment-Hinweise
- docs/releases.md Release-Ablauf und Tagging
- docs/cloudflare-tunnel.md aktives Tunnel- und Hostname-Setup
- docs/beta-cloudflared-daemon.md Beta-Betrieb mit Arcane und Cloudflared Daemon
- docs/data-migration.md Datenmigration von SQLite nach PostgreSQL

## Schnellstart

1. Repositories tt-auth, tt-members, tt-agenda, tt-analytics und tt-attendance lokal neben dieses Repo legen.
2. `.env.example` aus `scripts/render_platform_env.py` erzeugen und nach `.env` kopieren.
3. Stack starten.

```bash
docker compose -f docker-compose.yml -f docker-compose.local.yml up -d --build
```

## Deployment-Modi

- docker-compose.yml gemeinsamer Basis-Stack ohne oeffentliche App-Ports
- docker-compose.local.yml lokaler Direktzugriff ueber localhost:8085/8086/8087/8088
- docker-compose.arcane.beta.yml serverseitiger Beta-Stack fuer Arcane plus Cloudflared Daemon

## Versionierung und Releases

- jedes Repository fuehrt eine eigene `VERSION`
- Release-Tags folgen `vMAJOR.MINOR.PATCH`
- `main` erzeugt Beta-Images nach GHCR
- Produktion verwendet pro Service feste Release-Tags
- `tt-infra` dokumentiert und pinnt die Kombination der freigegebenen Service-Versionen
- freigegebene Produktionsstaende liegen als Release-Manifeste unter `releases/*.env`
- Release- und Env-Dateien werden aus `platform_config.py` und `scripts/render_platform_env.py` generiert

### Lokal auf dem Entwickler-Laptop

```bash
python scripts/render_platform_env.py render-env --profile local > .env.example
cp .env.example .env
docker compose -f docker-compose.yml -f docker-compose.local.yml up -d --build
```

## Beta auf Server

Beispiel fuer den laufenden Beta-Stack:

- beta.thun-tigers.net
- auth-beta.thun-tigers.net
- members-beta.thun-tigers.net
- agenda-beta.thun-tigers.net
- analytics-beta.thun-tigers.net
- attendance-beta.thun-tigers.net

Alle fachlichen Services verwenden denselben Einstieg:

- `/<service>/login` leitet auf `tt-auth` weiter
- `tt-auth` startet den SSO-Flow
- der Service nimmt das Token unter `/auth/sso` an und springt danach auf `/`

Start auf Server (mit vorhandener .env.arcane.beta):

```bash
docker compose --env-file .env.arcane.beta \
	-f docker-compose.yml \
	-f docker-compose.local.yml \
	-f docker-compose.arcane.beta.yml \
	up -d --build
```

## Hinweise

- Die Compose-Dateien verwenden fuer tt-auth, tt-members, tt-agenda, tt-analytics und tt-attendance relative Build-Pfade in benachbarte Repositories.
- Feste `container_name`-Eintraege wurden bewusst entfernt, damit lokale und spaetere Deployment-Kontexte nicht aneinanderkoppeln.
- Die Konfiguration laesst sich in `tt-infra` ueber `Admin -> Konfig` fuer die aktive Umgebung einsehen, bearbeiten und als `.env` exportieren.
- Fuer Beta-Betrieb uebernimmt der Cloudflared Daemon auf dem Server den externen Zugang.
- Die fachlichen Services folgen alle demselben Login- und SSO-Startpunkt.
- Wenn GHCR Pulls nicht verfuegbar sind, ist Source-Sync plus Build auf dem Server ein gueltiger Betriebsweg.

## Produktions-Releases

- `releases/0.1.0.env` ist der erste zentrale Plattform-Release
- `releases/0.1.8.env` ist der aktuelle freigegebene Plattform-Stand
- die Datei pinnt die freigegebenen Image-Tags fuer `tt-infra`, `tt-auth`, `tt-members`, `tt-agenda`, `tt-analytics` und `tt-attendance`
- die produktive Secret-Datei bleibt getrennt; das Release-Manifest liefert nur die Tag-Auswahl
