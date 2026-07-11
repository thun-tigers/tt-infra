# Release Manifeste

Dieses Verzeichnis pinnt freigegebene Plattform-Staende fuer deploybare Stacks.

Grundsatz:

- jede Datei `releases/X.Y.Z.env` beschreibt genau einen freigegebenen Plattform-Release
- neue Dateien enthalten genau einen gemeinsamen `TIGERS_VERSION`-Wert
- Secrets und abgeleitete Laufzeitwerte bleiben in `instance/runtime.env`

Beispiel:

- `releases/0.1.0.env` pinnt alle Services auf den gemeinsamen Start-Release `v0.1.0`
- `releases/0.1.20.env` pinnt den aktuellen Plattform-Stand auf `v0.1.20`

Verwendung mit Docker Compose:

```bash
docker compose \
  --env-file .env --env-file instance/runtime.env \
  -f compose.yml -f docker-compose.beta.yml \
  config
```

Verwendung in Arcane:

- Stack-Datei: `compose.yml` plus `docker-compose.beta.yml`
- Environment-Variablen aus der Stack-`.env` setzen
- zusaetzlich die Variablen aus dem gewuenschten Release-Manifest uebernehmen
- die Compose-Datei selbst muss fuer einen Versionssprung nicht angepasst werden, solange die Image-Tags ueber das Manifest kommen
- wenn Arcane nur eine Env-Datei akzeptiert, die Basis-Env mit dem Manifest vorab mergen, zum Beispiel mit `python scripts/render_arcane_env.py --base .env.arcane.beta --overlay releases/0.1.20.env --output .env.arcane.beta.v0.1.20`

Konvention:

- Dateiname ohne `v`, also `releases/0.1.0.env`
- neuer Inhalt mit `v`, also `TIGERS_VERSION=v0.1.0`
