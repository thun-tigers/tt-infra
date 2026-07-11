# Handoff: Zentrale Config & Reverse Proxy

Stand: 2026-07-08  
Übergabe von Claude (Sonnet 4.6) an Codex.

---

## 1. Zielbild

- **Eine Public Base URL pro Profil**: `PUBLIC_BASE_URL` ist der einzige konfigurierbare Einstieg.
- **Abgeleitete URLs**: `AUTH_BASE_URL` und `DEFAULT_*_URL` werden aus `PUBLIC_BASE_URL` berechnet und **nicht separat gepflegt**.
- **Internes Routing**: Services kommunizieren untereinander über Docker-DNS (`http://tt-service:5000`), nie über die öffentliche URL.
- **generated.env**: Internes Artefakt von tt-infra, wird per Script oder Config-UI erzeugt. Kein manuell gepflegtes Pendant in den Microservices.
- **Caddy als Reverse Proxy**: Eingehender Traffic läuft über `tt-proxy` (Caddy), der Pfad-Präfixe strippt und `X-Forwarded-Prefix` setzt.
- **ProxyFix in allen Services**: `werkzeug.middleware.proxy_fix.ProxyFix(x_for=1, x_proto=1, x_host=1, x_prefix=1)` ist in allen 6 Flask-Apps aktiv.

### Profil-Werte

| Profil | PUBLIC_BASE_URL |
|---|---|
| local | `http://localhost:8080` |
| beta | `https://beta.thun-tigers.net` |
| production | `https://thun-tigers.net` |

### Abgeleitete Werte (werden in generated.env geschrieben)

```
AUTH_BASE_URL         = {PUBLIC_BASE_URL}/auth
DEFAULT_MEMBERS_URL   = {PUBLIC_BASE_URL}/members
DEFAULT_AGENDA_URL    = {PUBLIC_BASE_URL}/agenda
DEFAULT_ANALYTICS_URL = {PUBLIC_BASE_URL}/analytics
DEFAULT_ATTENDANCE_URL= {PUBLIC_BASE_URL}/attendance
DEFAULT_INFRA_URL     = {PUBLIC_BASE_URL}/infra
```

---

## 2. Lokaler Workflow

```bash
cd ~/Repos/tigers/tt-infra

# Erststart
./setup.sh

# Neustart ohne Rebuild
./scripts/deploy.sh

# Neustart mit Rebuild
./scripts/deploy.sh --build

# Nur generated.env regenerieren
./scripts/generate-env.sh local
```

| URL | Beschreibung |
|---|---|
| http://localhost:8080 | Entry Point (Caddy Reverse Proxy) |
| http://localhost:8080/auth/ | tt-auth (Login, Dashboard) |
| http://localhost:8080/members/ | tt-members |
| http://localhost:8080/agenda/ | tt-agenda |
| http://localhost:8080/analytics/ | tt-analytics |
| http://localhost:8080/attendance/ | tt-attendance |
| http://localhost:8080/infra/ | tt-infra |
| http://localhost:8080/infra/config | Config-UI |

Direkte Ports 8084–8089 sind noch aktiv (werden später entfernt).

### Smoke-Tests lokal

```bash
curl -si http://localhost:8080/auth/     | grep -E '^(HTTP|Location)'
# HTTP/1.1 302 Found
# Location: /auth/login?next=/

curl -si http://localhost:8080/members/ | grep -E '^(HTTP|Location)'
# HTTP/1.1 302 Found
# Location: /members/login?next=http://localhost:8080/members/
```

---

## 3. Beta Workflow

### Vorbedingungen

1. `instance/platform-config.json` und `instance/secrets.local.json` auf dem Beta-Server werden von der Config-UI befüllt.
2. Cloudflare Tunnel ist konfiguriert: `beta.thun-tigers.net` → `http://host.docker.internal:80` (zeigt auf Caddy, **nicht** mehr auf einzelne Service-Ports).

### Beta-Deploy (Neuaufbau)

```bash
# Auf dem Beta-Server:
cd /opt/tigers/tt-infra

# Secrets in der Config-UI setzen (einmalig, danach werden `instance/platform-config.json` und `instance/secrets.local.json` exportiert)
# Dann:
./scripts/generate-env.sh beta
docker compose \
  --env-file ./instance/generated.env \
  -f docker-compose.arcane.beta.yml \
  up -d --build
```

### Erwartete generated.env für Beta

```dotenv
PUBLIC_BASE_URL=https://beta.thun-tigers.net
AUTH_BASE_URL=https://beta.thun-tigers.net/auth
DEFAULT_MEMBERS_URL=https://beta.thun-tigers.net/members
DEFAULT_AGENDA_URL=https://beta.thun-tigers.net/agenda
DEFAULT_ANALYTICS_URL=https://beta.thun-tigers.net/analytics
DEFAULT_ATTENDANCE_URL=https://beta.thun-tigers.net/attendance
DEFAULT_INFRA_URL=https://beta.thun-tigers.net/infra
JWT_COOKIE_DOMAIN=.thun-tigers.net
JWT_COOKIE_SECURE=true
```

### Cloudflare Tunnel: Neue Routing-Konfiguration

**Alt (Subdomain-basiert, pro Service):**
```
auth-beta.thun-tigers.net     → http://host.docker.internal:6085
members-beta.thun-tigers.net  → http://host.docker.internal:6088
agenda-beta.thun-tigers.net   → http://host.docker.internal:6086
analytics-beta.thun-tigers.net→ http://host.docker.internal:6087
attendance-beta.thun-tigers.net→http://host.docker.internal:6089
```

**Neu (Pfad-basiert, ein Einstieg):**
```
beta.thun-tigers.net          → http://host.docker.internal:80  (Caddy)
```

Caddy (`Caddyfile.beta`) routet dann intern:
- `/auth/*`       → `tt-auth:5000`
- `/members/*`    → `tt-members:5000`
- `/agenda/*`     → `tt-agenda:5000`
- `/analytics/*`  → `tt-analytics:5000`
- `/attendance/*` → `tt-attendance:5000`
- `/infra/*`      → `tt-infra:5000`

Caddy setzt `X-Forwarded-Prefix` pro Service — ProxyFix in den Flask-Apps liest diesen Header und setzt `SCRIPT_NAME` korrekt.

### Beta-DB Neuaufbau

Beta darf vollständig neu aufgebaut werden — Testdaten sind akzeptabler Verlust.

```bash
# Alte Volumes entfernen (auf dem Beta-Server):
docker compose -f docker-compose.arcane.beta.yml down -v

# Neu starten — DB wird automatisch angelegt (AUTO_CREATE_DB=true)
./scripts/generate-env.sh beta
docker compose \
  --env-file ./instance/generated.env \
  -f docker-compose.arcane.beta.yml \
  up -d --build
```

tt-auth legt beim ersten Start neue Service-Einträge mit den Pfad-basierten URLs an (`CREATE_DEFAULT_SERVICES=true`). Kein manuelles Re-Seeding nötig.

---

## 4. Aktueller Stand / Erledigt

| Was | Status |
|---|---|
| `instance/` Bind Mount für tt-infra | ✓ |
| `generated.env` schreiben via Config-UI | ✓ |
| `scripts/generate-env.sh` | ✓ |
| `scripts/deploy.sh` | ✓ |
| `setup.sh` (Erststart) | ✓ |
| `platform_config.py`: `PUBLIC_BASE_URL` Ableitung für alle 3 Profile | ✓ |
| Config-UI: abgeleitete Felder nur als read-only (`Abgeleitet`-Badge) | ✓ |
| Caddy `tt-proxy` lokal (Port 8080) | ✓ |
| `Caddyfile.local` mit `handle_path` + `X-Forwarded-Prefix` | ✓ |
| `Caddyfile.beta` (bereit, noch nicht live) | ✓ |
| `tt-proxy` Service in `docker-compose.arcane.beta.yml` | ✓ |
| ProxyFix in allen 6 Flask-Services | ✓ |
| `request.url` (statt `request.path`) in Login-Guards | ✓ tt-analytics, tt-attendance, tt-infra |
| Beta Compose: `AUTH_BASE_URL` Fallbacks korrigiert (mit `/auth`) | ✓ |
| Beta Compose: `DEFAULT_INFRA_URL` nicht mehr hardcoded | ✓ |
| Beta Compose: `DEFAULT_*_URL` Fallbacks auf Pfad-URLs | ✓ |
| SSO End-to-End lokal über `localhost:8080` verifiziert | ✓ alle 5 Services |
| Keine alten Ports (8084–8089) im öffentlichen Flow | ✓ verifiziert |

---

## 5. Noch offen

| Was | Priorität | Hinweis |
|---|---|---|
| **Beta neu deployen** (Cloudflare Tunnel umstellen) | Hoch | Nächster Schritt für Codex |
| **Beta SSO End-to-End testen** | Hoch | Nach Neuaufbau |
| Lokale direkte Ports 8084–8089 entfernen | Mittel | Erst nach Beta-Verifikation |
| Secrets bereinigen (`change-me-*`) | Mittel | Nur in Config-UI, nie in Git |
| `:-` Fallbacks für Secrets aus Compose entfernen | Mittel | Sicherheitsverbesserung |
| Startup-Validation (`require_env()`) in Services | Niedrig | Über tt-common |
| `env_file:` Blöcke in `docker-compose.arcane.beta.yml` | Niedrig | Nice-to-have, generated.env via `--env-file` reicht |
| `beta-cloudflared-daemon.md` aktualisieren | Niedrig | Routing-Doku für neues Schema |

---

## 6. Wichtige Invarianten

Diese Regeln dürfen nicht verletzt werden:

1. **Keine Microservice-`.env`-Dateien**: Services beziehen alle Vars aus `generated.env` (via `--env-file` oder `env_file:` in Compose). Keine manuell gepflegten Dateien in den Service-Repos.
2. **Keine hardcodierten Public Service URLs**: `AUTH_BASE_URL`, `DEFAULT_*_URL` etc. kommen immer aus `generated.env`. Hardcodierte Fallbacks (z.B. `:-http://localhost:8085`) in Python-Code sind Notfallwerte und dürfen nicht aktiv genutzt werden.
3. **Interne URLs bleiben intern**: `TT_*_INTERNAL_URL = http://tt-service:5000` (Docker-DNS). Diese URLs sind nur für Service-zu-Service-Kommunikation.
4. **generated.env ist schreibgeschützt**: Nur `generate-env.sh` oder die Config-UI schreiben diese Datei. Nie manuell bearbeiten.
5. **PUBLIC_BASE_URL ist der einzige editierbare Einstieg**: Alle 6 abgeleiteten URLs folgen daraus. Config-UI zeigt sie als read-only an.
6. **ProxyFix bleibt in allen Services aktiv**: `x_for=1, x_proto=1, x_host=1, x_prefix=1`. Nie entfernen, solange Caddy vor den Services sitzt.
7. **Caddy setzt X-Forwarded-Prefix**: Ohne diesen Header funktioniert `url_for()` mit SCRIPT_NAME nicht korrekt.

---

## 7. Architektur-Übersicht

```
Browser / Cloudflared
        ↓ HTTPS (Cloudflare terminiert TLS)
        ↓ HTTP  (intern)
    Caddy :80 (tt-proxy)
        ├── /auth/*       → tt-auth:5000
        ├── /members/*    → tt-members:5000
        ├── /agenda/*     → tt-agenda:5000
        ├── /analytics/*  → tt-analytics:5000
        ├── /attendance/* → tt-attendance:5000
        └── /infra/*      → tt-infra:5000
                ↑ alle mit X-Forwarded-Prefix + ProxyFix
```

```
tt-auth (Seeding beim Start)
    CREATE_DEFAULT_SERVICES=true
    →  services.url = DEFAULT_*_URL aus generated.env
    →  Pfad-basierte URLs werden beim Start automatisch gesetzt/aktualisiert
```

---

## 8. Dateien die Codex kennen muss

| Datei | Zweck |
|---|---|
| `platform_config.py` | Zentrale Konfig-Quelle, definiert alle Env-Vars pro Profil |
| `instance/platform-config.json` | Laufzeit-Overrides ohne Secrets, gitignored |
| `instance/secrets.local.json` | Laufzeit-Secrets, gitignored |
| `instance/generated.env` | Gerendertes Artefakt für Docker Compose, gitignored |
| `scripts/generate-env.sh` | Erzeugt `generated.env` ohne laufenden Stack |
| `scripts/deploy.sh` | Startet Stack mit `generated.env` |
| `setup.sh` | Erststart (generate + deploy --build) |
| `Caddyfile.local` | Caddy-Config lokal |
| `Caddyfile.beta` | Caddy-Config beta (bereit, noch nicht live) |
| `docker-compose.yml` | Basis-Stack (lokal + beta Grundlage) |
| `docker-compose.arcane.beta.yml` | Beta-Overrides (Images, beta DBs, tt-proxy) |
| `app/routes/config.py` | Config-UI Backend |
| `app/templates/config/index.html` | Config-UI Frontend |
