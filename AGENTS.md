# AGENTS.md

## Zweck

Diese Datei enthält die gemeinsamen Arbeitsregeln und den Projektkontext für Coding Agents, die an der Thun-Tigers-Plattform arbeiten.

Sie gilt für:

- Codex
- Claude Code
- GitHub Copilot
- Hermes
- zukünftige weitere Agents

Tool-spezifische Dateien wie `CLAUDE.md`, `HERMES.md` oder `.github/copilot-instructions.md` sollen nur auf diese Datei verweisen und kleine Ergänzungen enthalten.

## Organisation

- GitHub Organisation: `thun-tigers`
- Project / Kanban: `Tigers Platform Roadmap`
- Project URL: `https://github.com/orgs/thun-tigers/projects/1`
- Primäres Steuerungsrepo: `thun-tigers/tt-infra`

## Repositories

Steuerungs-/Infrastrukturrepo:

- `thun-tigers/tt-infra`

Service-Repos:

- `thun-tigers/tt-auth`
- `thun-tigers/tt-members`
- `thun-tigers/tt-agenda`
- `thun-tigers/tt-analytics`
- `thun-tigers/tt-attendance`
- `thun-tigers/tt-common`

Hinweis:
Weitere Repos können später dazukommen. Bei neuen Repos diese Liste aktualisieren.

## Aktueller Architekturstand

- Aktueller Release-Stand: `v0.1.16`
- Local Entry Point: `http://localhost:8080`
- Beta Entry Point: `https://beta.thun-tigers.net`
- Zentrale Config-Schicht liegt in `tt-infra`
- `PUBLIC_BASE_URL` ist die zentrale Public URL pro Profil
- `AUTH_BASE_URL` und `DEFAULT_*_URL` werden aus `PUBLIC_BASE_URL` abgeleitet
- `runtime.env` ist ein automatisch generiertes internes Artefakt
- Microservices sollen keine eigenen manuell gepflegten `.env`-Dateien benötigen
- Services kommunizieren intern über Docker-DNS, z.B. `http://tt-auth:5000`
- Nach aussen soll langfristig nur ein Entry Point sichtbar sein
- Local nutzt Caddy/`tt-proxy` auf Port `8080`
- Beta ist für Pfad-Routing über `https://beta.thun-tigers.net` vorbereitet

## Wichtige Dokumente

Vor grösseren Änderungen lesen:

- `README.md`
- `docs/CONFIG_UI_AND_RUNTIME_ENV.md`
- `platform_config.py`
- `compose.yml`
- `docker-compose.beta.yml`
- `caddy-local/Caddyfile`
- `caddy/Caddyfile`

## Issue- und Project-Arbeitsweise

- GitHub Issues sind die primäre Aufgabenquelle.
- Cross-cutting Infrastruktur-, Architektur- und Ops-Themen bevorzugt in `thun-tigers/tt-infra` anlegen.
- Service-spezifische Themen im jeweiligen Service-Repo anlegen.
- Das GitHub Project / Kanban heisst `Tigers Platform Roadmap`.
- Neue Issues sollen, wenn möglich, dem Project hinzugefügt werden.
- Falls ein Agent das Project nicht direkt bearbeiten kann, soll er das Issue trotzdem korrekt im passenden Repo erstellen und erwähnen, dass es manuell oder per Project-Workflow hinzugefügt werden muss.
- Issue-Titel kurz und handlungsorientiert halten.
- Issue-Bodies sollen Ziel, Kontext, Akzeptanzkriterien und Nicht-Ziele enthalten.

## Empfohlene Labels

Falls Labels existieren, bevorzugt nutzen:

- `area:infra`
- `area:auth`
- `area:members`
- `area:agenda`
- `area:analytics`
- `area:attendance`
- `area:ops`
- `area:beta`
- `priority:high`
- `priority:normal`
- `status:blocked`

Falls Labels nicht existieren, nicht scheitern; stattdessen im Issue-Body erwähnen.

## Arbeitsregeln

- Vor grösseren Änderungen zuerst einen kurzen Plan liefern.
- Kleine, testbare Commits bevorzugen.
- Keine Big-Bang-Migrationen.
- Keine Secrets committen.
- Keine Runtime-Dateien committen.
- Nie committen:
  - `instance/runtime.env`
  - `secrets.local.json`
  - `.env`
- Keine neuen manuell gepflegten `.env`-Dateien in Microservices einführen.
- Konfiguration bevorzugt zentral in `tt-infra` lösen.
- Fehlende Config-Werte nicht durch neue hardcodierte Defaults in Microservices kaschieren.
- Bei Multi-Repo-Änderungen am Ende in jedem betroffenen Repo `git status` prüfen.
- Vor Release-Cuts prüfen, dass keine generierten Dateien, Secrets oder lokalen Testdaten im Git landen.
- Beta-Testdaten dürfen bei Bedarf verworfen werden, aber das muss explizit dokumentiert werden.
- Production nicht ohne explizite Freigabe migrieren.

## Lokaler Standardworkflow

```bash
cd tt-infra
./scripts/generate-env.sh local
./scripts/deploy.sh --build
```
