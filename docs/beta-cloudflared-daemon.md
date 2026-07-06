# Beta-Server mit Arcane und Cloudflared

Ziel: Der Beta-Server `46.62.153.114` betreibt den Tigers-Stack mit Docker Compose. Cloudflared routet die bereits konfigurierten Cloudflare-Domains auf die lokalen Service-Ports. Arcane bleibt nur das Docker-Verwaltungswerkzeug und wird nicht oeffentlich veroeffentlicht.

## Routing

Wenn Cloudflared als Docker-Container laeuft, sollte Cloudflare Tunnel auf diese Ziele zeigen:

```text
beta.thun-tigers.net             -> http://host.docker.internal:6085
auth-beta.thun-tigers.net        -> http://host.docker.internal:6085
members-beta.thun-tigers.net     -> http://host.docker.internal:6088
agenda-beta.thun-tigers.net      -> http://host.docker.internal:6086
analytics-beta.thun-tigers.net   -> http://host.docker.internal:6087
attendance-beta.thun-tigers.net  -> http://host.docker.internal:6089
```

`beta.thun-tigers.net` und `auth-beta.thun-tigers.net` zeigen beide auf `tt-auth`. `beta.thun-tigers.net` ist der zentrale Einstieg in die Plattform.

Die Compose-Datei bindet diese Ports standardmaessig auf `172.17.0.1`, also die Docker-Bridge-IP, die `host.docker.internal` im Cloudflared-Container erreicht. Wenn Cloudflared wirklich als Host-Daemon ohne Container laeuft, kann `TT_HOST_BIND_IP=127.0.0.1` gesetzt und in Cloudflare Tunnel `http://localhost:608x` verwendet werden.

`tt-infra` braucht fuer SSO-Redirects `AUTH_BASE_URL=https://beta.thun-tigers.net`. Ohne diese Variable faellt der Login-Redirect auf den Default `http://localhost:8085` zurueck und der Browser landet in einer nicht erreichbaren Adresse.

Fuer manuelle Backups braucht `tt-infra` die Datenvolumes der anderen Services als Quellen. In der Beta-Compose werden `tt-members-data` und `analytics-uploads-data` deshalb in `tt-infra` auf `/backup-sources/tt-members-instance` und `/backup-sources/tt-analytics-uploads` gemountet.

## Arcane

Arcane braucht keinen oeffentlichen Hostname. Auf dem Server ist Arcane idealerweise nur lokal gebunden:

```text
127.0.0.1:3552 -> 3552
```

Zugriff vom Arbeitsplatz:

```bash
ssh -L 3552:127.0.0.1:3552 root@46.62.153.114
```

Dann lokal im Browser `http://127.0.0.1:3552` oeffnen.

## Compose-Stack

Empfohlener Pfad:

```bash
mkdir -p /opt/tigers
cd /opt/tigers
git clone git@github.com:thun-tigers/tt-infra.git
```

Die Arcane-Compose-Datei veroeffentlicht die Host-Ports im `608x`-Bereich auf `${TT_HOST_BIND_IP}`. Diese Ports sind die Ziele fuer Cloudflared:

```bash
cd /opt/tigers/tt-infra
docker compose --env-file .env.arcane.beta \
  -f docker-compose.arcane.beta.yml \
  pull

docker compose --env-file .env.arcane.beta \
  -f docker-compose.arcane.beta.yml \
  up -d
```

Wenn Arcane nur eine einzige Env-Datei akzeptiert, wird vor dem Import eine kombinierte Datei erzeugt:

```bash
python scripts/render_arcane_env.py \
  --base .env.arcane.beta \
  --overlay releases/0.1.6.env \
  --output .env.arcane.beta.v0.1.6
```

Danach zeigt Arcane auf `.env.arcane.beta.v0.1.6` statt auf zwei getrennte Dateien.

Status:

```bash
docker compose --env-file .env.arcane.beta \
  -f docker-compose.arcane.beta.yml \
  ps
```

## Environment

Auf dem Server muss `/opt/tigers/tt-infra/.env.arcane.beta` die echten Secrets enthalten. Fuer SSO und Cookies sind diese Werte wichtig:

```dotenv
JWT_COOKIE_DOMAIN=.thun-tigers.net
JWT_COOKIE_SECURE=true
TT_HOST_BIND_IP=172.17.0.1

DEFAULT_MEMBERS_URL=https://members-beta.thun-tigers.net
DEFAULT_AGENDA_URL=https://agenda-beta.thun-tigers.net
DEFAULT_ANALYTICS_URL=https://analytics-beta.thun-tigers.net
DEFAULT_ATTENDANCE_URL=https://attendance-beta.thun-tigers.net

MEMBERS_AUTH_BASE_URL=https://beta.thun-tigers.net
AGENDA_AUTH_BASE_URL=https://beta.thun-tigers.net
ANALYTICS_AUTH_BASE_URL=https://beta.thun-tigers.net
ATTENDANCE_AUTH_BASE_URL=https://beta.thun-tigers.net
```

`SSO_SHARED_SECRET` muss in allen Services identisch sein. `INTERNAL_API_SECRET` muss ebenfalls stackweit gleich sein.

## Firewall

Wenn Cloudflared als Container laeuft, muessen die App-Ports nur auf der Docker-Bridge-IP erreichbar sein. Empfohlen:

```text
22/tcp    offen fuer SSH
6085/tcp  gebunden an 172.17.0.1
6086/tcp  gebunden an 172.17.0.1
6087/tcp  gebunden an 172.17.0.1
6088/tcp  gebunden an 172.17.0.1
6089/tcp  gebunden an 172.17.0.1
3552/tcp  nur 127.0.0.1 fuer Arcane
```

Externer Benutzertraffic kommt ueber Cloudflare, nicht direkt ueber diese Ports.
