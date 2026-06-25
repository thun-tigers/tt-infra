# Cloudflare Tunnel mit Traefik

Dieses Dokument beschreibt den aktiven Beta-Betrieb mit Cloudflare Tunnel und Traefik.

## Zielbild

Die Kette lautet:

- Internet
- Cloudflare DNS und Edge
- `cloudflared`
- Traefik
- `tt-auth`, `tt-members`, `tt-agenda`, `tt-analytics`

Cloudflare und Traefik sind dabei nicht doppelt.

- Cloudflare ist fuer DNS, TLS, WAF und Tunnel-Zugang zustaendig.
- Traefik ist fuer das interne Hostname-Routing im Docker-Stack zustaendig.

## Aktive Beta-Hostnames

- auth-beta.thun-tigers.net
- members-beta.thun-tigers.net
- agenda-beta.thun-tigers.net
- analytics-beta.thun-tigers.net

## Routing-Prinzip

- Extern endet TLS bei Cloudflare.
- Cloudflared leitet HTTP-Requests in den Docker-Stack.
- Traefik routed nach Hostname auf die internen Services.
- Service-zu-Service Kommunikation laeuft intern im Compose-Netz.

## Cookie- und SSO-Hinweis

Fuer serviceuebergreifende Anmeldung und Theme-Sync muessen folgende Punkte konsistent sein:

- JWT_COOKIE_DOMAIN in Beta auf .thun-tigers.net
- identische SSO_SHARED_SECRET Werte in allen Services
- AUTH_BASE_URL und Service-URLs in tt-auth auf die beta-Hostnames gesetzt
