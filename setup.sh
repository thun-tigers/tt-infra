#!/usr/bin/env bash
# Bootstrap fuer tt-infra.
#
# Verwendungsmodelle:
# - lokal aus einem bestehenden Checkout: ./setup.sh
# - blanker Server: Script herunterladen, in /tmp ausfuehren und das Repo
#   automatisch nach /opt/tigers/tt-infra klonen
#
# Profile:
# - local: lokaler Docker-Stack neben den Service-Checkouts
# - beta: kompletter Server-Stack mit GHCR-Images
# - production: kompletter Produktions-Stack mit Release-Manifests

set -Eeuo pipefail

DEFAULT_REPO_URL="https://github.com/thun-tigers/tt-infra.git"
DEFAULT_REPO_DIR="${TT_INFRA_REPO_DIR:-/opt/tigers/tt-infra}"
DEFAULT_REPO_REF="${TT_INFRA_CLONE_REF:-main}"

PROFILE="${TT_INFRA_PROFILE:-}"
REPO_URL="${TT_INFRA_REPO_URL:-$DEFAULT_REPO_URL}"
REPO_DIR="$DEFAULT_REPO_DIR"
REPO_REF="$DEFAULT_REPO_REF"
PUBLIC_BASE_URL="${PUBLIC_BASE_URL:-}"
DEFAULT_ADMIN_USERNAME="${DEFAULT_ADMIN_USERNAME:-admin}"
DEFAULT_ADMIN_PASSWORD="${DEFAULT_ADMIN_PASSWORD:-}"
SKIP_CLONE="${TT_INFRA_SKIP_CLONE:-0}"

log() { printf '%s\n' "$*"; }
info() { printf '→ %s\n' "$*"; }
warn() { printf 'WARN: %s\n' "$*" >&2; }
die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

require_cmd() {
    command -v "$1" >/dev/null 2>&1 || die "Fehlendes Kommando: $1"
}

is_repo_root() {
    [ -f "$1/platform_config.py" ] && [ -f "$1/docker-compose.yml" ]
}

bootstrap_repo() {
    if is_repo_root "$REPO_DIR"; then
        return 0
    fi

    if [ "$SKIP_CLONE" = "1" ]; then
        die "Repo nicht gefunden: $REPO_DIR"
    fi

    require_cmd git
    mkdir -p "$(dirname "$REPO_DIR")"
    if [ -e "$REPO_DIR" ]; then
        if [ "$REPO_DIR" = "$SOURCE_DIR" ]; then
            die "Download bitte in ein anderes Verzeichnis legen, z.B. /tmp, oder TT_INFRA_REPO_DIR auf ein leeres Ziel setzen."
        fi
        if [ -n "$(find "$REPO_DIR" -mindepth 1 -maxdepth 1 -print -quit 2>/dev/null || true)" ]; then
            die "Zielverzeichnis ist nicht leer: $REPO_DIR"
        fi
    fi

    info "Klonen von $REPO_URL nach $REPO_DIR ..."
    git clone --depth 1 --branch "$REPO_REF" "$REPO_URL" "$REPO_DIR"
}

cleanup_on_error() {
    local exit_code=$?
    printf '\n' >&2
    warn "Setup fehlgeschlagen (Exit-Code ${exit_code})."
    if command -v docker >/dev/null 2>&1 && [ -f "$ENV_FILE" ]; then
        if docker compose version >/dev/null 2>&1; then
            warn "Aktueller Stack-Status:"
            (cd "$REPO_ROOT" && docker compose --env-file "$ENV_FILE" "${COMPOSE_FILES[@]}" ps) >&2 || true
            warn "Letzte Postgres-Logs:"
            (cd "$REPO_ROOT" && docker compose --env-file "$ENV_FILE" "${COMPOSE_FILES[@]}" logs --no-color --tail=80 tt-postgres) >&2 || true
        fi
    fi
    exit "$exit_code"
}

wait_for_postgres() {
    local timeout_seconds=180
    local deadline=$((SECONDS + timeout_seconds))

    info "Warte auf Postgres-Readiness ..."
    while [ "$SECONDS" -lt "$deadline" ]; do
        local container_id status
        container_id="$(cd "$REPO_ROOT" && docker compose --env-file "$ENV_FILE" "${COMPOSE_FILES[@]}" ps -q tt-postgres 2>/dev/null || true)"
        if [ -n "$container_id" ]; then
            status="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$container_id" 2>/dev/null || true)"
            if [ "$status" = "healthy" ]; then
                info "Postgres ist bereit."
                return 0
            fi
        fi
        sleep 2
    done

    die "Postgres wurde innerhalb von ${timeout_seconds}s nicht healthy."
}

seed_profile_store() {
    local profile="$1"
    local public_base_url="$2"
    local admin_username="$3"
    local admin_password="$4"
    local version="$5"

    python3 - "$STORE_PATH" "$profile" "$public_base_url" "$admin_username" "$admin_password" "$version" <<'PY'
from __future__ import annotations

import secrets
import sys
from pathlib import Path

repo_store = Path(sys.argv[1])
profile = sys.argv[2]
public_base_url = sys.argv[3].strip()
admin_username = sys.argv[4].strip() or 'admin'
admin_password = sys.argv[5].strip()
version = sys.argv[6].strip()

repo_root = repo_store.parents[1]
sys.path.insert(0, str(repo_root))

from platform_config import load_profile_store, profile_sections, profile_values, save_profile_store  # noqa: E402


def is_sensitive(key: str) -> bool:
    return any(marker in key for marker in ('SECRET', 'TOKEN', 'API_KEY')) or key.endswith('_PASSWORD')


def is_placeholder(value: str) -> bool:
    value = value or ''
    return not value or value.startswith('change-me') or value == 'admin'


def random_secret() -> str:
    return secrets.token_hex(32)


def derive_db_url(prefix: str, values: dict[str, str]) -> str:
    user_key = f'POSTGRES_{prefix}_USER'
    password_key = f'POSTGRES_{prefix}_PASSWORD'
    db_key = f'POSTGRES_{prefix}_DB'
    user = values.get(user_key) or ''
    password = values.get(password_key) or ''
    database = values.get(db_key) or ''
    return f'postgresql+psycopg://{user}:{password}@tt-postgres:5432/{database}'


store = load_profile_store(repo_store, seed_defaults=True)
defaults = profile_values(profile, version=version)
values = dict(store.get(profile, {}))
values.update(defaults)

if public_base_url:
    values['PUBLIC_BASE_URL'] = public_base_url.rstrip('/')

if profile == 'local' and not public_base_url:
    values['PUBLIC_BASE_URL'] = defaults.get('PUBLIC_BASE_URL', 'http://localhost:8080')

values['DEFAULT_ADMIN_USERNAME'] = admin_username or values.get('DEFAULT_ADMIN_USERNAME', 'admin') or 'admin'
    if admin_password:
        values['DEFAULT_ADMIN_PASSWORD'] = admin_password
    elif profile == 'local':
        values['DEFAULT_ADMIN_PASSWORD'] = values.get('DEFAULT_ADMIN_PASSWORD') or 'admin'
    elif is_placeholder(values.get('DEFAULT_ADMIN_PASSWORD', '')):
        values['DEFAULT_ADMIN_PASSWORD'] = random_secret()

for section in profile_sections(profile, version=version):
    for item in section.entries:
        key = item.key
        current = values.get(key, '')
        if key == 'PUBLIC_BASE_URL' and values.get(key):
            continue
        if key == 'DEFAULT_ADMIN_USERNAME':
            continue
        if key == 'DEFAULT_ADMIN_PASSWORD':
            continue
        if key.endswith('_DATABASE_URL'):
            continue
        if is_sensitive(key) and is_placeholder(current):
            values[key] = random_secret()
        elif item.required and current == '':
            values[key] = values.get(key, item.value)

for prefix in ('INFRA', 'AUTH', 'MEMBERS', 'AGENDA', 'ANALYTICS', 'ATTENDANCE'):
    url_key = f'{prefix}_DATABASE_URL'
    current = values.get(url_key, '')
    if not current or 'change-me' in current or 'tt-postgres' not in current:
        values[url_key] = derive_db_url(prefix, values)

store[profile] = values
save_profile_store(repo_store, store)

print(f'PUBLIC_BASE_URL={values.get("PUBLIC_BASE_URL", "")}')
print(f'DEFAULT_ADMIN_USERNAME={values.get("DEFAULT_ADMIN_USERNAME", "admin")}')
print(f'DEFAULT_ADMIN_PASSWORD={values.get("DEFAULT_ADMIN_PASSWORD", "")}')
PY
}

parse_args() {
    while [ "$#" -gt 0 ]; do
        case "$1" in
            -h|--help)
                cat <<'EOF'
Verwendung:
  ./setup.sh [local|beta|production]
  ./setup.sh --profile <local|beta|production>

Um einen blanken Server zu bootstrapen:
  TT_INFRA_REPO_DIR=/opt/tigers/tt-infra TT_INFRA_CLONE_REF=v0.1.20 ./setup.sh beta
EOF
                exit 0
                ;;
            --profile)
                [ "$#" -ge 2 ] || die "--profile braucht ein Argument"
                PROFILE="$2"
                shift 2
                ;;
            --repo-url)
                [ "$#" -ge 2 ] || die "--repo-url braucht ein Argument"
                REPO_URL="$2"
                shift 2
                ;;
            --repo-dir)
                [ "$#" -ge 2 ] || die "--repo-dir braucht ein Argument"
                REPO_DIR="$2"
                shift 2
                ;;
            --ref|--branch|--tag)
                [ "$#" -ge 2 ] || die "$1 braucht ein Argument"
                REPO_REF="$2"
                shift 2
                ;;
            --skip-clone)
                SKIP_CLONE=1
                shift
                ;;
            local|beta|production)
                PROFILE="$1"
                shift
                ;;
            *)
                die "Unbekanntes Argument: $1"
                ;;
        esac
    done
}

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
parse_args "$@"

if [ -z "$PROFILE" ]; then
    if is_repo_root "$SOURCE_DIR"; then
        PROFILE="local"
    else
        PROFILE="beta"
    fi
fi

bootstrap_repo
REPO_ROOT="$REPO_DIR"
INSTANCE_DIR="$REPO_ROOT/instance"
STORE_PATH="$INSTANCE_DIR/platform-config.json"
ENV_FILE="$INSTANCE_DIR/generated.env"

case "$PROFILE" in
    local)
        if [ -z "$PUBLIC_BASE_URL" ]; then
            PUBLIC_BASE_URL="http://localhost:8080"
        fi
        ;;
    beta)
        if [ -z "$PUBLIC_BASE_URL" ]; then
            PUBLIC_BASE_URL="https://beta.thun-tigers.net"
        fi
        ;;
    production)
        if [ -z "$PUBLIC_BASE_URL" ]; then
            PUBLIC_BASE_URL="https://thun-tigers.net"
        fi
        ;;
    *)
        die "Unbekanntes Profil: $PROFILE"
        ;;
esac

if [ ! -f "$REPO_ROOT/VERSION" ]; then
    die "VERSION-Datei fehlt im Repo: $REPO_ROOT"
fi
VERSION="$(tr -d '\n' < "$REPO_ROOT/VERSION")"

case "$PROFILE" in
    local)
        COMPOSE_FILES=(-f docker-compose.yml -f docker-compose.local.yml)
        ;;
    beta)
        COMPOSE_FILES=(-f docker-compose.beta.yml)
        ;;
    production)
        COMPOSE_FILES=(-f docker-compose.prod.yml)
        ;;
esac

trap cleanup_on_error ERR

require_cmd docker
require_cmd python3
docker info >/dev/null 2>&1 || die "Docker-Daemon laeuft nicht oder ist nicht erreichbar."
docker compose version >/dev/null 2>&1 || die "Docker Compose ist nicht verfuegbar."

cd "$REPO_ROOT"
mkdir -p "$INSTANCE_DIR"

if [ -t 0 ] && [ "$PROFILE" = "local" ]; then
    printf 'Public Base URL [%s]: ' "$PUBLIC_BASE_URL"
    read -r input_public_base_url || true
    PUBLIC_BASE_URL="${input_public_base_url:-$PUBLIC_BASE_URL}"

    printf 'Admin Username [%s]: ' "$DEFAULT_ADMIN_USERNAME"
    read -r input_admin_username || true
    DEFAULT_ADMIN_USERNAME="${input_admin_username:-$DEFAULT_ADMIN_USERNAME}"

    printf 'Admin Password [generated if empty]: '
    read -r -s input_admin_password || true
    printf '\n'
    DEFAULT_ADMIN_PASSWORD="${input_admin_password:-$DEFAULT_ADMIN_PASSWORD}"
fi

info "Initialisiere Konfigurationsstore fuer Profil '$PROFILE' ..."
seed_output="$(seed_profile_store "$PROFILE" "$PUBLIC_BASE_URL" "$DEFAULT_ADMIN_USERNAME" "$DEFAULT_ADMIN_PASSWORD" "$VERSION")"

GENERATED_PUBLIC_BASE_URL=""
GENERATED_ADMIN_USERNAME=""
GENERATED_ADMIN_PASSWORD=""
while IFS='=' read -r key value; do
    case "$key" in
        PUBLIC_BASE_URL) GENERATED_PUBLIC_BASE_URL="$value" ;;
        DEFAULT_ADMIN_USERNAME) GENERATED_ADMIN_USERNAME="$value" ;;
        DEFAULT_ADMIN_PASSWORD) GENERATED_ADMIN_PASSWORD="$value" ;;
    esac
done <<EOF
$seed_output
EOF

info "Erzeuge instance/generated.env ..."
"$REPO_ROOT/scripts/generate-env.sh" --version "$VERSION" "$PROFILE" >/dev/null

info "Starte Stack ..."
docker compose --env-file "$ENV_FILE" "${COMPOSE_FILES[@]}" up -d --build
wait_for_postgres

printf '\n'
log "=== Setup abgeschlossen ==="
printf '\n'
case "$PROFILE" in
    local)
        log "  Entry Point : http://localhost:8080"
        log "  Config-UI   : http://localhost:8080/infra/config"
        ;;
    beta)
        log "  Entry Point : https://beta.thun-tigers.net"
        log "  Config-UI   : https://beta.thun-tigers.net/infra/config"
        ;;
    production)
        log "  Entry Point : https://thun-tigers.net"
        log "  Config-UI   : https://thun-tigers.net/infra/config"
        ;;
esac
printf '\n'
log "Gespeicherte Konfiguration:"
log "  Repo        : $REPO_ROOT"
log "  Store       : $STORE_PATH"
log "  generated.env: $ENV_FILE"
printf '\n'
log "Initiale Login-Daten:"
log "  Benutzer    : ${GENERATED_ADMIN_USERNAME:-$DEFAULT_ADMIN_USERNAME}"
if [ -n "$GENERATED_ADMIN_PASSWORD" ]; then
    log "  Passwort    : $GENERATED_ADMIN_PASSWORD"
else
    log "  Passwort    : (nicht neu generiert)"
fi
