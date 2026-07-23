# Datenmigration SQLite nach PostgreSQL

Hinweis: Alle Postgres-Datenbanken laufen inzwischen in einem gemeinsamen Container `tt-postgres` (siehe `docs/CONFIG_UI_AND_RUNTIME_ENV.md`). Die untenstehenden Kommandos beziehen sich auf einzelne Datenbanken (`tt_auth`, `tt_agenda`, ...) innerhalb dieses Containers.

## Status

Die Anwendungen `tt-auth`, `tt-agenda` und `tt-attendance` sind fuer PostgreSQL vorbereitet. Die vorhandenen SQLite-Daten liegen aktuell hier:

- `../tt-auth/instance/auth.db`
- `../tt-agenda/instance/trainings.db`
- `tt-attendance` hat keinen SQLite-Standardpfad mehr; sie nutzt jetzt die Datenbank `tt_attendance` in `tt-postgres`

Aktueller Datenbestand:

- `tt-auth`: 1 Benutzer, 0 Services
- `tt-agenda`: 12 Trainings, 113 Activities, 1 Training Instance, 10 Activity Instances, 5 Activity Types, 2 Benutzer
- `tt-attendance`: neue Postgres-Datenbank, Migration nur bei vorhandenen Alt-Daten noetig

Zusatz:

- In `tt-agenda` gibt es die Legacy-Tabelle `training_type` mit 3 Eintraegen. Diese wird nicht mehr von der aktuellen App verwendet und wird bei der Migration als JSON archiviert.

## Voraussetzungen

- Docker Desktop oder ein laufender Docker-Daemon
- `docker compose up -d tt-postgres` in tt-infra (legt alle Service-Datenbanken beim ersten Start via Init-Script an)
- Python mit `psycopg` verfuegbar

## Postgres starten

```bash
cd /Users/swisi/Repos/tigers/tt-infra
docker compose up -d tt-postgres
```

## Zielschema initialisieren

Da `tt-auth` kein Alembic-Setup hat, reicht ein App-Start mit `AUTO_CREATE_DB=true`.

Fuer `tt-auth`:

```bash
cd /Users/swisi/Repos/tigers/tt-auth
docker compose up -d tt-auth
```

Fuer `tt-agenda`:

```bash
cd /Users/swisi/Repos/tigers/tt-agenda
docker compose up -d web
```

## Migration ausfuehren

### tt-auth

```bash
cd /Users/swisi/Repos/tigers/tt-infra
python3 scripts/migrate_tt_auth_sqlite_to_postgres.py \
  --sqlite-path ../tt-auth/instance/auth.db \
  --postgres-dsn postgresql://tt_auth:tt_auth_password@localhost:5432/tt_auth
```

### tt-agenda

```bash
cd /Users/swisi/Repos/tigers/tt-infra
python3 scripts/migrate_tt_agenda_sqlite_to_postgres.py \
  --sqlite-path ../tt-agenda/instance/trainings.db \
  --postgres-dsn postgresql://tt_agenda:tt_agenda_password@localhost:5432/tt_agenda \
  --archive-dir ./migration-archive/tt-agenda
```

## Verifikation

Nach der Migration:

- bei `tt-auth` mit dem bisherigen Admin-User einloggen
- in `tt-agenda` Trainings, Activities und Benutzer pruefen
- danach erst produktive SQLite-Nutzung deaktivieren

## Backups

Die produktiven Postgres-Daten liegen im gemeinsamen Docker-Volume `postgres-data` des Containers `tt-postgres`. Der Cluster enthaelt die Datenbanken `tt_auth`, `tt_members`, `tt_agenda`, `tt_attendance`, `tt_analytics` und `tt_infra`.

Empfohlene Backups:

- regelmaessige `pg_dump`-Jobs
- optional zusaetzliche Host-/Storage-Snapshots der Volumes

## Wichtiger Hinweis

Die Migrationstransfers sind destruktiv fuer die Zieltabellen:

- das Ziel in PostgreSQL wird vor dem Import per `TRUNCATE ... RESTART IDENTITY CASCADE` geleert
- den Lauf daher nur gegen frische oder bewusst zu ueberschreibende Ziel-Datenbanken verwenden
