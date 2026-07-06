# Release Manifeste

Dieses Verzeichnis pinnt freigegebene Plattform-Staende fuer deploybare Stacks.

Grundsatz:

- jede Datei `releases/X.Y.Z.env` beschreibt genau einen freigegebenen Plattform-Release
- die Datei enthaelt ausschliesslich die Image-Tags der deploybaren Services
- die eigentlichen Secrets und Betriebsparameter bleiben in der produktiven `.env`

Beispiel:

- `releases/0.1.0.env` pinnt alle Services auf den gemeinsamen Start-Release `v0.1.0`
- `releases/0.1.6.env` pinnt den Beta-Stack auf `v0.1.6`

Verwendung mit Docker Compose:

```bash
docker compose \
  --env-file .env.arcane.beta \
  --env-file releases/0.1.6.env \
  -f docker-compose.arcane.beta.yml \
  config
```

Verwendung in Arcane:

- Stack-Datei: `docker-compose.arcane.beta.yml`
- Environment-Variablen aus der Stack-`.env` setzen
- zusaetzlich die Variablen aus dem gewuenschten Release-Manifest uebernehmen
- die Compose-Datei selbst muss fuer einen Versionssprung nicht angepasst werden, solange die Image-Tags ueber das Manifest kommen
- wenn Arcane nur eine Env-Datei akzeptiert, die Basis-Env mit dem Manifest vorab mergen, zum Beispiel mit `python scripts/render_arcane_env.py --base .env.arcane.beta --overlay releases/0.1.6.env --output .env.arcane.beta.v0.1.6`

Konvention:

- Dateiname ohne `v`, also `releases/0.1.0.env`
- enthaltene Tags mit `v`, also `TT_AUTH_IMAGE_TAG=v0.1.0`
