# Release Manifeste

Dieses Verzeichnis pinnt freigegebene Plattform-Staende fuer deploybare Stacks.

Grundsatz:

- jede Datei `releases/X.Y.Z.env` beschreibt genau einen freigegebenen Plattform-Release
- die Datei enthaelt ausschliesslich die Image-Tags der deploybaren Services
- die eigentlichen Secrets und Betriebsparameter bleiben in der produktiven `.env`

Beispiel:

- `releases/0.1.0.env` pinnt alle Services auf den gemeinsamen Start-Release `v0.1.0`

Verwendung mit Docker Compose:

```bash
docker compose \
  --env-file .env.arcane.beta \
  --env-file releases/0.1.0.env \
  -f docker-compose.arcane.beta.yml \
  config
```

Verwendung in Arcane:

- Stack-Datei: `docker-compose.arcane.beta.yml`
- Environment-Variablen aus der Stack-`.env` setzen
- zusaetzlich die Variablen aus dem gewuenschten Release-Manifest uebernehmen

Konvention:

- Dateiname ohne `v`, also `releases/0.1.0.env`
- enthaltene Tags mit `v`, also `TT_AUTH_IMAGE_TAG=v0.1.0`
