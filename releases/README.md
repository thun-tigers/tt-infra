# Release Manifeste

Dieses Verzeichnis pinnt freigegebene Plattform-Staende fuer Produktion.

Grundsatz:

- jede Datei `releases/X.Y.Z.env` beschreibt genau einen freigegebenen Plattform-Release
- die Datei enthaelt ausschliesslich die Image-Tags der deploybaren Services
- die eigentlichen Secrets und Betriebsparameter bleiben in der produktiven `.env`

Beispiel:

- `releases/0.1.0.env` pinnt alle Services auf den gemeinsamen Start-Release `v0.1.0`

Verwendung mit Docker Compose:

```bash
docker compose \
  --env-file .env.production \
  --env-file releases/0.1.0.env \
  -f docker-compose.portainer.production.yml \
  config
```

Verwendung in Portainer:

- Stack-Datei: `docker-compose.portainer.production.yml`
- Environment-Variablen aus der produktiven `.env` setzen
- zusaetzlich die Variablen aus dem gewuenschten Release-Manifest uebernehmen

Konvention:

- Dateiname ohne `v`, also `releases/0.1.0.env`
- enthaltene Tags mit `v`, also `TT_AUTH_IMAGE_TAG=v0.1.0`
