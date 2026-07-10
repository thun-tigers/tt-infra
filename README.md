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

## Schnellstart (lokal)

1. Repositories tt-auth, tt-members, tt-agenda, tt-analytics und tt-attendance lokal neben dieses Repo legen.
2. Stack mit einem Befehl starten — `generated.env` wird automatisch erstellt:

```bash
./setup.sh
```

Oder manuell:

```bash
./scripts/generate-env.sh local
./scripts/deploy.sh --build
```

**Lokaler Entry Point:** `http://localhost:8080`

| Pfad | Service |
|---|---|
| http://localhost:8080/auth/ | tt-auth (Login, Dashboard) |
| http://localhost:8080/members/ | tt-members |
| http://localhost:8080/agenda/ | tt-agenda |
| http://localhost:8080/analytics/ | tt-analytics |
| http://localhost:8080/attendance/ | tt-attendance |
| http://localhost:8080/infra/ | tt-infra (Config-UI, Admin) |

Die direkten Service-Ports (8084–8089) sind lokal noch aktiv und koennen parallel verwendet werden.

## Deployment-Modi

- docker-compose.yml zentraler Stack mit Caddy-Reverse-Proxy (Port 8080) und direkten Service-Ports
- docker-compose.local.yml optionale Port-Variablen fuer Entwicklung
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
./setup.sh                         # Erststart: env generieren + Stack bauen
./scripts/deploy.sh                # Neustart ohne Rebuild
./scripts/deploy.sh --build        # Neustart mit Rebuild
./scripts/generate-env.sh local    # Nur generated.env aktualisieren
```

Config-UI (Secrets, URLs, Profil-Werte): `http://localhost:8080/infra/config`

### URL-Ableitung

Der einzige konfigurierbare Public-URL-Einstieg ist **`PUBLIC_BASE_URL`** (z.B. `http://localhost:8080`).
Alle weiteren Public URLs werden zur Laufzeit automatisch abgeleitet und sind nicht separat editierbar:

| Variable | Abgeleitet als |
|---|---|
| `AUTH_BASE_URL` | `{PUBLIC_BASE_URL}/auth` |
| `DEFAULT_MEMBERS_URL` | `{PUBLIC_BASE_URL}/members` |
| `DEFAULT_AGENDA_URL` | `{PUBLIC_BASE_URL}/agenda` |
| `DEFAULT_ANALYTICS_URL` | `{PUBLIC_BASE_URL}/analytics` |
| `DEFAULT_ATTENDANCE_URL` | `{PUBLIC_BASE_URL}/attendance` |
| `DEFAULT_INFRA_URL` | `{PUBLIC_BASE_URL}/infra` |

Alle abgeleiteten Werte stehen weiterhin in `instance/generated.env` (Abwaertskompatibilitaet) und werden von Docker Compose und tt-auth beim Start eingelesen.
Die Config-UI zeigt die abgeleiteten Felder als schreibgeschuetzt an ("Abgeleitet"-Badge).

## Beta auf Server

Entry Point: `https://beta.thun-tigers.net`

| Pfad | Service |
|---|---|
| https://beta.thun-tigers.net/auth/ | tt-auth |
| https://beta.thun-tigers.net/members/ | tt-members |
| https://beta.thun-tigers.net/agenda/ | tt-agenda |
| https://beta.thun-tigers.net/analytics/ | tt-analytics |
| https://beta.thun-tigers.net/attendance/ | tt-attendance |
| https://beta.thun-tigers.net/infra/ | tt-infra |

Alle fachlichen Services verwenden denselben Einstieg:

- `/<service>/login` leitet auf `/auth/` weiter
- `tt-auth` startet den SSO-Flow
- der Service nimmt das Token unter `/auth/sso` an und springt danach auf `/`

Start auf Server (mit vorhandener `instance/generated.env`, siehe [`docs/HANDOFF_CENTRAL_CONFIG_AND_PROXY.md`](docs/HANDOFF_CENTRAL_CONFIG_AND_PROXY.md)):

```bash
./scripts/generate-env.sh beta
docker compose \
	--env-file ./instance/generated.env \
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
- `releases/0.1.16.env` ist der aktuelle freigegebene Plattform-Stand
- die Datei pinnt die freigegebenen Image-Tags fuer `tt-infra`, `tt-auth`, `tt-members`, `tt-agenda`, `tt-analytics` und `tt-attendance`
- die produktive Secret-Datei bleibt getrennt; das Release-Manifest liefert nur die Tag-Auswahl
