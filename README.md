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

## Zielbild

tt-auth ist der zentrale Identity- und Access-Service.
tt-infra betreibt den Compose-Stack, Netzwerk, Umgebungen und Betriebsprozesse.
Fachliche Anwendungen wie tt-members, tt-agenda und tt-analytics laufen als eigene Services.

## Struktur

- docker-compose.yml zentraler Compose-Stack
- docker-compose.local.yml lokale Port-Freigaben fuer Entwicklung
- docker-compose.edge.yml Edge-Variante mit Traefik und cloudflared
- .env.example Vorlage fuer lokale und serverseitige Umgebungsvariablen
- docs/architecture.md Zielarchitektur und Standards
- docs/stack-architecture.md detaillierte Plattform-Architektur
- docs/operations.md Betriebs- und Deployment-Hinweise
- docs/releases.md Release-Ablauf und Tagging
- docs/cloudflare-tunnel.md aktives Tunnel- und Hostname-Setup
- docs/data-migration.md Datenmigration von SQLite nach PostgreSQL

## Schnellstart

1. Repositories tt-auth, tt-members, tt-agenda und tt-analytics lokal neben dieses Repo legen.
2. .env.example nach .env kopieren und Werte setzen.
3. Stack starten.

```bash
docker compose -f docker-compose.yml -f docker-compose.local.yml up -d --build
```

## Deployment-Modi

- docker-compose.yml gemeinsamer Basis-Stack ohne oeffentliche App-Ports
- docker-compose.local.yml lokaler Direktzugriff ueber localhost:8085/8086/8087/8088
- docker-compose.edge.yml Ingress ueber Traefik plus cloudflared
- docker-compose.beta.yml serverseitige Beta-Overrides (nicht im Repo versioniert)

## Versionierung und Releases

- jedes Repository fuehrt eine eigene `VERSION`
- Release-Tags folgen `vMAJOR.MINOR.PATCH`
- `main` erzeugt Beta-Images nach GHCR
- Produktion verwendet pro Service feste Release-Tags
- `tt-infra` dokumentiert und pinnt die Kombination der freigegebenen Service-Versionen
- freigegebene Produktionsstaende liegen als Release-Manifeste unter `releases/*.env`

### Lokal auf dem Entwickler-Laptop

```bash
cp .env.example .env
docker compose -f docker-compose.yml -f docker-compose.local.yml up -d --build
```

## Beta auf Server

Beispiel fuer den laufenden Beta-Stack:

- auth-beta.thun-tigers.net
- members-beta.thun-tigers.net
- agenda-beta.thun-tigers.net
- analytics-beta.thun-tigers.net

Start auf Server (mit vorhandener .env.beta):

```bash
docker compose --env-file .env.beta \
	-f docker-compose.yml \
	-f docker-compose.local.yml \
	-f docker-compose.beta.yml \
	up -d --build
```

## Hinweise

- Die Compose-Dateien verwenden fuer tt-auth, tt-members, tt-agenda und tt-analytics relative Build-Pfade in benachbarte Repositories.
- Feste `container_name`-Eintraege wurden bewusst entfernt, damit lokale und spaetere Deployment-Kontexte nicht aneinanderkoppeln.
- Fuer Edge-Betrieb uebernimmt Cloudflare den externen Zugang, waehrend Traefik intern per Hostname an die Services weiterleitet.
- Wenn GHCR Pulls nicht verfuegbar sind, ist Source-Sync plus Build auf dem Server ein gueltiger Betriebsweg.

## Produktions-Releases

- `releases/0.1.0.env` ist der erste zentrale Plattform-Release
- die Datei pinnt die freigegebenen Image-Tags fuer `tt-infra`, `tt-auth`, `tt-members`, `tt-agenda` und `tt-analytics`
- die produktive Secret-Datei bleibt getrennt; das Release-Manifest liefert nur die Tag-Auswahl
