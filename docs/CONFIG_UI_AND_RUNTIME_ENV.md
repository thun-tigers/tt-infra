# Config-UI und runtime.env — Datenfluss

Ersetzt die im Zuge von v0.1.23 geloeschte `HANDOFF_CENTRAL_CONFIG_AND_PROXY.md`.
Diese Version beschreibt den aktuellen, reparierten Stand (die Web-UI unter
`/infra/config` war zwischen v0.1.23 und dem Fix in dieser Doku von der
Bereitstellung abgekoppelt — Speichern schrieb `instance/generated.env`, aber
nichts las diese Datei).

## Ablauf

```
platform_config.py (Profil-Kataloge lokal/beta/production)
        │
        ▼
config_store.py (Postgres-Tabellen platform_settings/platform_secrets)
        │  Web-UI /infra/config: lesen/bearbeiten/speichern
        ▼
instance/generated.env  (nicht-Secret-Werte, siehe app/routes/config.py::_write_generated_env)
        │
        ▼
scripts/render_platform_env.py generate   ◄── zusaetzlich: OPERATOR_KEYS aus os.environ,
        │                                      Secrets aus vorhandener runtime.env /
        │                                      secrets.local.json / neu erzeugt
        ▼
instance/runtime.env  (nur Schluessel, die compose.yml tatsaechlich als ${VAR} referenziert)
        │
        ▼
docker compose --env-file .env --env-file instance/runtime.env -f compose.yml ... up -d
```

## Prioritaet beim Rendern (`generate`-Kommando)

Niedrig → hoch:

1. Profil-Default aus `platform_config.py`
2. Wert aus `instance/generated.env` (Web-UI-Save), **ausser** Secrets und
   `PUBLIC_DERIVED_KEYS`
3. bereits vorhandener Wert in `instance/runtime.env` bzw. Legacy
   `instance/secrets.local.json` — gilt nur fuer Secrets, verhindert dass ein
   veraltetes `generated.env` ein bereits rotiertes Secret ueberschreibt
4. `OPERATOR_KEYS`-Shell-Override (`.env`, z. B. `PUBLIC_BASE_URL`)
5. von `PUBLIC_BASE_URL` abgeleitete URLs (`AUTH_BASE_URL`, `DEFAULT_*_URL`)

## Blank-Server-Bootstrapping

`instance/generated.env` existiert auf einem frischen Checkout nicht — der
Postgres-Container (der die Web-UI-Werte speichert) existiert zu diesem
Zeitpunkt ebenfalls noch nicht. `render_platform_env.py generate` liest daher
niemals live aus der Datenbank, sondern ausschliesslich aus der Datei. Fehlt
sie, verhaelt sich der Bootstrap exakt wie vor diesem Fix.

## Wichtig fuer Operator:innen

Eine Aenderung in `/infra/config` wirkt **nicht sofort**. Sie wird erst nach

```bash
./scripts/generate-env.sh <profil>
./scripts/deploy.sh
```

auf dem Server aktiv (Container-Restart mit neuem `instance/runtime.env`). Die
Web-UI startet den Stack nicht selbst neu.

## Bekannte, bewusst nicht editierbare Felder

- `POSTGRES_*_DB`: wird aus Servicename + `DATABASE_SUFFIX` zusammengesetzt,
  keine direkte Interpolation (Risiko: doppelter Suffix). Eine echte
  Datenbank-Umbenennung braucht ohnehin eine Migration.
- `TT_*_INTERNAL_URL` / `DEFAULT_*_INTERNAL_URL`: Docker-interne DNS-Namen,
  die exakt den Servicenamen in `compose.yml` entsprechen — kein sinnvoll
  eigenstaendig konfigurierbarer Wert.
- `*_PORT`: nur fuer lokale Host-Port-Freigaben relevant, liegen in
  `docker-compose.local.yml`.
- `REDIS_URL`: durch die pro Service granulareren `RATELIMIT_STORAGE_URI` /
  `SSO_REPLAY_STORAGE_URI` ersetzt.

Ein Regressionstest (`tests/test_compose_env_sync.py`) prueft, dass jeder
andere Katalog-Schluessel tatsaechlich als `${VAR}` in `compose.yml`
referenziert wird.
