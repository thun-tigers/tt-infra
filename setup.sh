#!/usr/bin/env bash
# Bootstrap fuer tt-infra.
#
# Ziel:
# - im aktuellen Verzeichnis arbeiten
# - kein git clone benoetigen
# - auf einem leeren VPS optional ein Archiv direkt in das Zielverzeichnis
#   entpacken
#
# Profile:
# - local
# - beta
# - production

set -Eeuo pipefail

WORKDIR="${TT_INFRA_WORKDIR:-$PWD}"
PROFILE="${TT_INFRA_PROFILE:-}"
ARCHIVE_REF="${TT_INFRA_ARCHIVE_REF:-main}"
ARCHIVE_URL="${TT_INFRA_ARCHIVE_URL:-https://github.com/thun-tigers/tt-infra/archive/refs/heads/${ARCHIVE_REF}.tar.gz}"
PUBLIC_BASE_URL="${PUBLIC_BASE_URL:-}"
DEFAULT_ADMIN_USERNAME="${DEFAULT_ADMIN_USERNAME:-admin}"
DEFAULT_ADMIN_PASSWORD="${DEFAULT_ADMIN_PASSWORD:-}"

log() { printf '%s\n' "$*"; }
info() { printf '→ %s\n' "$*"; }
warn() { printf 'WARN: %s\n' "$*" >&2; }
die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

require_cmd() {
    command -v "$1" >/dev/null 2>&1 || die "Fehlendes Kommando: $1"
}

is_repo_root() {
    [ -f "$1/platform_config.py" ] && [ -f "$1/docker-compose.yml" ] && [ -f "$1/scripts/generate-env.sh" ]
}

ensure_source_tree() {
    if is_repo_root "$WORKDIR"; then
        return 0
    fi

    mkdir -p "$WORKDIR"

    if [ -n "$(find "$WORKDIR" -mindepth 1 -maxdepth 1 ! -name 'setup.sh' -print -quit 2>/dev/null || true)" ]; then
        die "Aktuelles Verzeichnis ist nicht leer und enthaelt noch keinen tt-infra-Checkout: $WORKDIR"
    fi

    info "Lade tt-infra-Archiv in $WORKDIR ..."
    if command -v curl >/dev/null 2>&1 && command -v tar >/dev/null 2>&1; then
        curl -fsSL "$ARCHIVE_URL" | tar -xz --strip-components=1 -C "$WORKDIR"
        return 0
    fi

    if command -v docker >/dev/null 2>&1; then
        docker run --rm -v "$WORKDIR:/work" -w /work alpine:3.20 sh -ec "
            apk add --no-cache curl tar >/dev/null
            curl -fsSL '$ARCHIVE_URL' | tar -xz --strip-components=1 -C /work
        "
        return 0
    fi

    die "Weder curl+tar noch Docker sind verfuegbar, um das Archiv zu laden."
}

cleanup_on_error() {
    local exit_code=$?
    printf '\n' >&2
    warn "Setup fehlgeschlagen (Exit-Code ${exit_code})."
    if command -v docker >/dev/null 2>&1 && [ -f "$ENV_FILE" ]; then
        if docker compose version >/dev/null 2>&1; then
            warn "Aktueller Stack-Status:"
            (cd "$WORKDIR" && docker compose --env-file "$ENV_FILE" "${COMPOSE_FILES[@]}" ps) >&2 || true
            warn "Letzte Postgres-Logs:"
            (cd "$WORKDIR" && docker compose --env-file "$ENV_FILE" "${COMPOSE_FILES[@]}" logs --no-color --tail=80 tt-postgres) >&2 || true
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
        container_id="$(cd "$WORKDIR" && docker compose --env-file "$ENV_FILE" "${COMPOSE_FILES[@]}" ps -q tt-postgres 2>/dev/null || true)"
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
    user = values.get(f'POSTGRES_{prefix}_USER') or ''
    password = values.get(f'POSTGRES_{prefix}_PASSWORD') or ''
    database = values.get(f'POSTGRES_{prefix}_DB') or ''
    return f'postgresql+psycopg://{user}:{password}@tt-postgres:5432/{database}'


store = load_profile_store(repo_store, seed_defaults=True)
defaults = profile_values(profile, version=version)
values = dict(store.get(profile, {}))
values.update(defaults)

if public_base_url:
    values['PUBLIC_BASE_URL'] = public_base_url.rstrip('/')
elif profile == 'local':
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
        if key in {'PUBLIC_BASE_URL', 'DEFAULT_ADMIN_USERNAME', 'DEFAULT_ADMIN_PASSWORD'}:
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

Wenn das aktuelle Verzeichnis noch leer ist:
  TT_INFRA_ARCHIVE_URL=https://github.com/thun-tigers/tt-infra/archive/refs/tags/v0.1.20.tar.gz ./setup.sh beta
EOF
                exit 0
                ;;
            --profile)
                [ "$#" -ge 2 ] || die "--profile braucht ein Argument"
                PROFILE="$2"
                shift 2
                ;;
            --archive-url)
                [ "$#" -ge 2 ] || die "--archive-url braucht ein Argument"
                ARCHIVE_URL="$2"
                shift 2
                ;;
            --archive-ref)
                [ "$#" -ge 2 ] || die "--archive-ref braucht ein Argument"
                ARCHIVE_REF="$2"
                ARCHIVE_URL="https://github.com/thun-tigers/tt-infra/archive/refs/heads/${ARCHIVE_REF}.tar.gz"
                shift 2
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

parse_args "$@"
ensure_source_tree

WORKDIR="$(cd "$WORKDIR" && pwd)"
REPO_ROOT="$WORKDIR"
INSTANCE_DIR="$REPO_ROOT/instance"
STORE_PATH="$INSTANCE_DIR/platform-config.json"
ENV_FILE="$INSTANCE_DIR/generated.env"

case "$PROFILE" in
    local)
        PUBLIC_BASE_URL="${PUBLIC_BASE_URL:-http://localhost:8080}"
        COMPOSE_FILES=(-f docker-compose.yml -f docker-compose.local.yml)
        ;;
    beta)
        PUBLIC_BASE_URL="${PUBLIC_BASE_URL:-https://beta.thun-tigers.net}"
        COMPOSE_FILES=(-f docker-compose.beta.yml)
        ;;
    production)
        PUBLIC_BASE_URL="${PUBLIC_BASE_URL:-https://thun-tigers.net}"
        COMPOSE_FILES=(-f docker-compose.prod.yml)
        ;;
    *)
        die "Unbekanntes Profil: $PROFILE"
        ;;
esac

if [ ! -f "$REPO_ROOT/VERSION" ]; then
    die "VERSION-Datei fehlt im aktuellen Verzeichnis: $REPO_ROOT"
fi
VERSION="$(tr -d '\n' < "$REPO_ROOT/VERSION")"

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

GENERATED_ADMIN_USERNAME="$DEFAULT_ADMIN_USERNAME"
GENERATED_ADMIN_PASSWORD="$DEFAULT_ADMIN_PASSWORD"
while IFS='=' read -r key value; do
    case "$key" in
        PUBLIC_BASE_URL) PUBLIC_BASE_URL="$value" ;;
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
log "  Verzeichnis : $REPO_ROOT"
log "  Store       : $STORE_PATH"
log "  generated.env: $ENV_FILE"
printf '\n'
log "Initiale Login-Daten:"
log "  Benutzer    : ${GENERATED_ADMIN_USERNAME:-$DEFAULT_ADMIN_USERNAME}"
if [ -n "${GENERATED_ADMIN_PASSWORD:-}" ]; then
    log "  Passwort    : $GENERATED_ADMIN_PASSWORD"
else
    log "  Passwort    : (nicht neu generiert)"
fi
