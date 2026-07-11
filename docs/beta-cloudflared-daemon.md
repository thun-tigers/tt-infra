# Beta-Server mit Arcane und Cloudflared

Hinweis: Die verbindliche Referenz fuer Deploy und Routing ist `docs/HANDOFF_CENTRAL_CONFIG_AND_PROXY.md`. Dieses Dokument beschreibt nur den Server- und Cloudflared-Kontext.

Ziel: Der Beta-Server `46.62.153.114` betreibt den Tigers-Stack mit Docker Compose. Cloudflared routet die Beta-Domain pfad-basiert auf den Caddy-Reverse-Proxy (`tt-proxy`) im Stack. Arcane bleibt nur das Docker-Verwaltungswerkzeug und wird nicht oeffentlich veroeffentlicht.

## Routing

Cloudflare Tunnel zeigt auf den lokalen Caddy-Proxy. Nur eine Zieladresse ist noetig:

```text
beta.thun-tigers.net             -> http://host.docker.internal:80
```

`host.docker.internal:80` erreicht den Caddy-Container `tt-proxy` (Port-Mapping `8080:80` lokal, in Beta wird `80` durch Cloudflared angesteuert). Caddy (`Caddyfile.beta`) routet dann intern pfad-basiert:

- `/auth/*`       -> `tt-auth:5000`
- `/members/*`    -> `tt-members:5000`
- `/agenda/*`     -> `tt-agenda:5000`
- `/analytics/*`  -> `tt-analytics:5000`
- `/attendance/*` -> `tt-attendance:5000`
- `/infra/*`      -> `tt-infra:5000`

Caddy setzt `X-Forwarded-Prefix`; ProxyFix in den Flask-Apps liest den Header und setzt `SCRIPT_NAME` korrekt.

`beta.thun-tigers.net` ist der zentrale Einstieg. `beta.thun-tigers.net/auth/` fuehrt zu `tt-auth`.

Historisches Modell (nicht mehr aktiv): Separate Subdomains `auth-beta.thun-tigers.net`, `members-beta.thun-tigers.net` usw. mit direkter Weiterleitung auf die Service-Ports `608x`. Cloudflare-Konfiguration und Firewall-Regeln fuer diese Ports werden nicht mehr benoetigt.

`tt-infra` braucht fuer SSO-Redirects `PUBLIC_BASE_URL=https://beta.thun-tigers.net`; daraus werden `AUTH_BASE_URL` und die uebrigen `DEFAULT_*_URL` in `runtime.env` abgeleitet.

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

Deploy-Ablauf (siehe HANDOFF-Dokument):

```bash
cd /opt/tigers/tt-infra
./scripts/generate-env.sh beta
docker compose \
  --env-file ./.env --env-file ./instance/runtime.env \
  -f compose.yml -f docker-compose.beta.yml \
  up -d
```

Wenn Arcane nur eine einzige Env-Datei akzeptiert, wird vor dem Import eine kombinierte Datei erzeugt, z.B.:

```bash
python scripts/render_arcane_env.py \
  --base ./instance/runtime.env \
  --overlay releases/0.1.16.env \
  --output .env.arcane.beta.v0.1.16
```

Status:

```bash
docker compose \
  --env-file ./.env --env-file ./instance/runtime.env \
  -f compose.yml -f docker-compose.beta.yml \
  ps
```

## Environment

Die Betreiberwerte liegen in `.env`; `instance/runtime.env` wird daraus mit automatisch verwalteten Secrets durch `scripts/generate-env.sh beta` erzeugt.

```dotenv
PUBLIC_BASE_URL=https://beta.thun-tigers.net
AUTH_BASE_URL=https://beta.thun-tigers.net/auth
DEFAULT_MEMBERS_URL=https://beta.thun-tigers.net/members
DEFAULT_AGENDA_URL=https://beta.thun-tigers.net/agenda
DEFAULT_ANALYTICS_URL=https://beta.thun-tigers.net/analytics
DEFAULT_ATTENDANCE_URL=https://beta.thun-tigers.net/attendance
DEFAULT_INFRA_URL=https://beta.thun-tigers.net/infra
JWT_COOKIE_DOMAIN=.thun-tigers.net
JWT_COOKIE_SECURE=true
```

`SSO_SHARED_SECRET` muss in allen Services identisch sein. `INTERNAL_API_SECRET` muss ebenfalls stackweit gleich sein.

## Firewall

Der oeffentliche Traffic kommt ausschliesslich ueber Cloudflare Tunnel. Auf dem Host muessen nur folgende Ports offen sein:

```text
22/tcp    offen fuer SSH
3552/tcp  nur 127.0.0.1 fuer Arcane
```

Die frueheren Bindings `6085`-`6089` fuer einzelne Service-Ports werden nicht mehr benoetigt und koennen entfernt werden. Der Caddy-Proxy nimmt intern per `host.docker.internal:80` alle Requests entgegen.
