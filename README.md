# tt-Inffra

Infrastruktur-, Operations- und Plattform-Repository fuer den Tigers Microservice-Stack.

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

`tt-auth` ist der zentrale Identity- und Access-Service. `tt-infra` stellt zentrale Stammdaten und Infrastruktur-APIs bereit. Fachliche Anwendungen wie `tt-members`, `tt-agenda` und `tt-analytics` werden als eigenstaendige Services betrieben und ueber den zentralen Stack orchestriert.

## Struktur

- `docker-compose.yml` zentraler Compose-Stack
- `.env.example` lokale Vorlagendatei fuer die benoetigten Umgebungsvariablen
- `docs/architecture.md` Zielarchitektur
- `docs/stack-architecture.md` detaillierte Plattform-Architektur
- `docs/operations.md` Betriebs- und Deployment-Hinweise
- `docs/cloudflare-tunnel.md` spaeteres Tunnel- und Hostname-Setup
- `docs/data-migration.md` Datenmigration von SQLite nach PostgreSQL

## Schnellstart

1. Repositories fuer `tt-auth`, `tt-members`, `tt-agenda` und `tt-analytics` lokal neben dieses Repo legen oder als externe Images verwenden.
2. `.env.example` nach `.env` kopieren und Werte setzen.
3. Pfade oder Image-Namen im `docker-compose.yml` anpassen.
4. Lokalen Stack starten:

```bash
docker compose -f docker-compose.yml -f docker-compose.local.yml up -d --build
```

## Deployment-Modi

- `docker-compose.yml`: gemeinsamer Basis-Stack ohne oeffentliche App-Ports
- `docker-compose.local.yml`: lokaler Direktzugriff ueber `localhost:8085/8086/8087/8088`
- `docker-compose.edge.yml`: vorbereiteter Ingress ueber Traefik plus `cloudflared`

### Lokal auf dem Entwickler-Laptop

```bash
cp .env.example .env
docker compose -f docker-compose.yml -f docker-compose.local.yml up -d --build
```

Spätere Deployment-Profile kommen in ein separates Deployment-Dokument, sobald der Server-Prozess definiert ist.

## Hinweise

- Die Compose-Dateien verwenden fuer `tt-auth`, `tt-members`, `tt-agenda` und `tt-analytics` relative Build-Pfade in benachbarte Repositories.
- Feste `container_name`-Eintraege wurden bewusst entfernt, damit lokale und spaetere Deployment-Kontexte nicht aneinanderkoppeln.
- Fuer Edge-Betrieb uebernimmt Cloudflare den externen Zugang, waehrend Traefik intern per Hostname an die Services weiterleitet.
