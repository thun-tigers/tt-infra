# Cloudflare Tunnel mit Caddy

Hinweis: Die verbindliche Referenz fuer das aktuelle Routing- und Proxy-Modell ist `docs/HANDOFF_CENTRAL_CONFIG_AND_PROXY.md`. Dieses Dokument fasst nur die Cloudflare-seitige Sicht zusammen.

Dieses Dokument beschreibt den aktiven Beta-Betrieb mit Cloudflare Tunnel und dem Caddy-Reverse-Proxy (`tt-proxy`).

## Zielbild

Die Kette lautet:

- Internet
- Cloudflare DNS und Edge
- `cloudflared`
- Caddy (`tt-proxy`, Image `caddy:2-alpine`, Port `8080:80`)
- `tt-auth`, `tt-members`, `tt-agenda`, `tt-analytics`, `tt-attendance`, `tt-infra`

Cloudflare und Caddy sind dabei nicht doppelt.

- Cloudflare ist fuer DNS, TLS, WAF und Tunnel-Zugang zustaendig.
- Caddy ist fuer das interne Pfad-Routing im Docker-Stack zustaendig und setzt `X-Forwarded-Prefix`.

## Aktive Beta-Einstiegspunkte

Pfad-basiertes Routing unter einer einzigen Domain:

- `https://beta.thun-tigers.net/auth/`
- `https://beta.thun-tigers.net/members/`
- `https://beta.thun-tigers.net/agenda/`
- `https://beta.thun-tigers.net/analytics/`
- `https://beta.thun-tigers.net/attendance/`
- `https://beta.thun-tigers.net/infra/`

## Routing-Prinzip

- Extern endet TLS bei Cloudflare.
- Cloudflared leitet HTTP-Requests auf Caddy (`http://host.docker.internal:80`).
- Caddy routet pfad-basiert (`Caddyfile.beta`) auf die internen Service-Container (`tt-auth:5000`, `tt-members:5000` usw.).
- Service-zu-Service Kommunikation laeuft intern im Compose-Netz `tigers-internal`.

## Cookie- und SSO-Hinweis

Fuer serviceuebergreifende Anmeldung und Theme-Sync muessen folgende Punkte konsistent sein:

- `JWT_COOKIE_DOMAIN` in Beta auf `.thun-tigers.net`
- identische `SSO_SHARED_SECRET` Werte in allen Services
- `PUBLIC_BASE_URL=https://beta.thun-tigers.net` (daraus werden `AUTH_BASE_URL` und `DEFAULT_*_URL` in `generated.env` abgeleitet)
