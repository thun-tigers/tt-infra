# Operations

## Lokale Entwicklung

Voraussetzungen:

- Docker und Docker Compose
- lokale Checkouts von `tt-auth`, `tt-members`, `tt-agenda` und `tt-analytics` neben diesem Repository

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
  tt-infra/
```

## Wichtige Hinweise

- `tt-auth` und `tt-agenda` muessen auf `SQLALCHEMY_DATABASE_URI` aus der Umgebung reagieren.
- `tt-members` und `tt-analytics` sind fester Bestandteil des Standard-Stacks.

## Persistenz und Backups

Die Datenbanken laufen in eigenen Docker-Volumes:

- `postgres-auth-data`
- `postgres-agenda-data`
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

## Naechste Plattform-Schritte

- Redis fuer Rate Limiting und Jobs hinzufuegen
- Deployment-Prozess fuer virtuellen Server definieren
- CI/CD fuer Compose-Validierung und Deployment ergaenzen

## Reverse Proxy und Tunnel

- Cloudflare bleibt der externe Edge-Layer fuer DNS, TLS, WAF und Tunnel-Terminierung.
- `cloudflared` bringt den Traffic in den Docker-Stack.
- Traefik bleibt intern sinnvoll und ist nicht doppelt: es uebernimmt Hostname-Routing, Docker-Service-Discovery und Ingress-Logik zwischen `tt-auth`, `tt-agenda` und `tt-analytics`.
- Pfadbasiertes Routing wurde bewusst nicht als Standardmodell gewaehlt, weil die bestehenden Apps sauberer ueber eigene Subdomains betrieben werden koennen.
- Eine konkrete Schritt-fuer-Schritt-Anleitung fuer externen Betrieb folgt spaeter in einem eigenen Deployment-Dokument.
