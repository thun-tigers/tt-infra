#!/usr/bin/env bash
# Bootstrap für eine neue lokale tt-infra-Installation.
#
# Phase 1:
# - lokale Voraussetzungen prüfen
# - instance/ initialisieren
# - lokalen Konfigurationsstore seeden
# - Secrets automatisch generieren
# - generated.env daraus ableiten
# - Postgres zuerst starten und auf Readiness warten
# - danach den restlichen Stack starten
#
# Verwendung:
#   ./setup.sh

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR" && pwd)"
INSTANCE_DIR="$REPO_ROOT/instance"
STORE_PATH="$INSTANCE_DIR/platform-config.json"
ENV_FILE="$INSTANCE_DIR/generated.env"

log() { printf '%s\n' "$*"; }
info() { printf '→ %s\n' "$*"; }
warn() { printf 'WARN: %s\n' "$*" >&2; }
die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

cleanup_on_error() {
    local exit_code=$?
    printf '\n' >&2
    warn "Setup fehlgeschlagen (Exit-Code ${exit_code})."
    if command -v docker >/dev/null 2>&1; then
        if docker compose version >/dev/null 2>&1; then
            warn "Aktueller Postgres-Status:"
            (cd "$REPO_ROOT" && docker compose --env-file "$ENV_FILE" -f docker-compose.yml -f docker-compose.local.yml ps tt-postgres) >&2 || true
            warn "Letzte Postgres-Logs:"
            (cd "$REPO_ROOT" && docker compose --env-file "$ENV_FILE" -f docker-compose.yml -f docker-compose.local.yml logs --no-color --tail=80 tt-postgres) >&2 || true
        fi
    fi
    exit "$exit_code"
}
trap cleanup_on_error ERR

require_cmd() {
    command -v "$1" >/dev/null 2>&1 || die "Fehlendes Kommando: $1"
}

compose_args() {
    local -a args
    args=(-f docker-compose.yml)
    if [ -f "$REPO_ROOT/docker-compose.local.yml" ]; then
        args+=(-f docker-compose.local.yml)
    fi
    printf '%s\n' "${args[@]}"
}

wait_for_postgres() {
    local timeout_seconds=120
    local deadline=$((SECONDS + timeout_seconds))
    local compose_files=()
    local arg
    while IFS= read -r arg; do
        compose_files+=("$arg")
    done < <(compose_args)

    info "Warte auf Postgres-Readiness ..."
    while [ "$SECONDS" -lt "$deadline" ]; do
        local container_id status
        container_id="$(cd "$REPO_ROOT" && docker compose --env-file "$ENV_FILE" "${compose_files[@]}" ps -q tt-postgres 2>/dev/null || true)"
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

seed_local_store() {
    local public_base_url="$1"
    local admin_username="$2"
    local admin_password="$3"

    python3 - "$STORE_PATH" "$public_base_url" "$admin_username" "$admin_password" <<'PY'
from __future__ import annotations

import secrets
import sys
from pathlib import Path

repo_store = Path(sys.argv[1])
public_base_url = sys.argv[2].rstrip('/') or 'http://localhost:8080'
admin_username = sys.argv[3] or 'admin'
admin_password = sys.argv[4]

repo_root = repo_store.parents[1]
sys.path.insert(0, str(repo_root))
from platform_config import load_profile_store, profile_sections, profile_values, save_profile_store  # noqa: E402


def is_sensitive(key: str) -> bool:
    return any(marker in key for marker in ('SECRET', 'TOKEN', 'API_KEY')) or key.endswith('_PASSWORD')


store = load_profile_store(repo_store, seed_defaults=True)
defaults = profile_values('local')
local = dict(store.get('local', {}))
local['PUBLIC_BASE_URL'] = public_base_url
local['DEFAULT_ADMIN_USERNAME'] = admin_username
if admin_password:
    local['DEFAULT_ADMIN_PASSWORD'] = admin_password
elif not local.get('DEFAULT_ADMIN_PASSWORD'):
    local['DEFAULT_ADMIN_PASSWORD'] = 'admin'

for section in profile_sections('local'):
    for item in section.entries:
        key = item.key
        if key == 'DEFAULT_ADMIN_PASSWORD' or not item.required or not is_sensitive(key):
            continue
        current_value = local.get(key, '')
        default_value = defaults.get(key, '')
        if current_value and current_value != default_value and not current_value.startswith('change-me'):
            continue
        local[key] = secrets.token_hex(32)

# Keep optional values unset unless the user filled them explicitly.
store['local'] = local
save_profile_store(repo_store, store)

print(f"OK: seeded {repo_store}")
PY
}

if [ ! -d "$REPO_ROOT" ]; then
    die "Repo root nicht gefunden: $REPO_ROOT"
fi

require_cmd docker
require_cmd python3
docker info >/dev/null 2>&1 || die "Docker-Daemon läuft nicht oder ist nicht erreichbar."
docker compose version >/dev/null 2>&1 || die "Docker Compose ist nicht verfügbar."

cd "$REPO_ROOT"

for required_file in docker-compose.yml scripts/generate-env.sh scripts/deploy.sh scripts/render_platform_env.py platform_config.py; do
    [ -f "$required_file" ] || die "Erforderliche Datei fehlt: $required_file"
done

mkdir -p "$INSTANCE_DIR"

PUBLIC_BASE_URL="${PUBLIC_BASE_URL:-http://localhost:8080}"
DEFAULT_ADMIN_USERNAME="${DEFAULT_ADMIN_USERNAME:-admin}"
DEFAULT_ADMIN_PASSWORD="${DEFAULT_ADMIN_PASSWORD:-}"

if [ -t 0 ]; then
    printf 'Environment [local]: '
    read -r _env_choice || true

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

info "Initialisiere lokalen Konfigurationsstore ..."
seed_local_store "$PUBLIC_BASE_URL" "$DEFAULT_ADMIN_USERNAME" "$DEFAULT_ADMIN_PASSWORD" >/dev/null

info "Erzeuge instance/generated.env ..."
"$SCRIPT_DIR/scripts/generate-env.sh" local >/dev/null

info "Starte zuerst Postgres ..."
docker compose --env-file "$ENV_FILE" -f docker-compose.yml -f docker-compose.local.yml up -d tt-postgres
wait_for_postgres

info "Starte restlichen Stack ..."
docker compose --env-file "$ENV_FILE" -f docker-compose.yml -f docker-compose.local.yml up -d --build

printf '\n'
log "=== Setup abgeschlossen ==="
printf '\n'
log "  Entry Point : http://localhost:8080"
log "  Config-UI   : http://localhost:8080/infra/config"
printf '\n'
log "Gespeicherte Konfiguration:"
log "  Store       : $STORE_PATH"
log "  generated.env: $ENV_FILE"
printf '\n'
log "Der Admin-Passwortwert steht im Store und kann in der Config-UI angepasst werden."
