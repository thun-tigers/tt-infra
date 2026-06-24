# Cloudflare Tunnel mit Traefik

Dieses Dokument bleibt vorerst als Entwurf fuer einen spaeteren externen Deployment-Prozess bestehen.
Fuer den aktuellen Arbeitsstand ist der lokale Stack mit `.env.example` und `docker-compose.local.yml` die relevante Variante.

## Zielbild

Die Kette lautet:

- Internet
- Cloudflare DNS und Edge
- `cloudflared`
- Traefik
- `tt-auth`, `tt-agenda`, `tt-analytics`

Cloudflare und Traefik sind dabei nicht doppelt.

- Cloudflare ist fuer DNS, TLS, WAF und Tunnel-Zugang zustaendig.
- Traefik ist fuer das interne Hostname-Routing im Docker-Stack zustaendig.

## Spaetere Deployment-Richtung

Wenn ein virtueller Server dazukommt, wird der externe Betrieb wieder sauber getrennt dokumentiert:

- eigene `.env` fuer den Deployment-Kontext
- eigener Tunnel- oder Ingress-Prozess
- eigene Domain-Zuordnung
- eigene Secret-Verwaltung

Bis dahin ist die lokale Compose-Variante die einzige relevante Betriebsform.
