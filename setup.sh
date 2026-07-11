#!/usr/bin/env bash
# Interaktiver Bootstrap fuer tt-infra.
#
# Ziel:
# - im aktuellen Verzeichnis arbeiten
# - kein git clone benoetigen
# - bei leerem Verzeichnis das tt-infra-Archiv direkt dort entpacken
# - eine minimale .env erzeugen und den Stack starten
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
ADMIN_USERNAME="${DEFAULT_ADMIN_USERNAME:-admin}"
ADMIN_PASSWORD="${DEFAULT_ADMIN_PASSWORD:-}"

log() { printf '%s\n' "$*"; }
info() { printf '→ %s\n' "$*"; }
warn() { printf 'WARN: %s\n' "$*" >&2; }
die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

require_cmd() {
    command -v "$1" >/dev/null 2>&1 || die "Fehlendes Kommando: $1"
}

random_hex() {
    local length="${1:-64}"
    tr -dc 'a-f0-9' </dev/urandom | head -c "$length"
}

normalize_base_url() {
    local input="${1:-}"
    input="${input%/}"
    case "$input" in
        http://*|https://*)
            printf '%s\n' "$input"
            ;;
        *)
            case "$PROFILE" in
                local) printf 'http://%s\n' "$input" ;;
                *) printf 'https://%s\n' "$input" ;;
            esac
            ;;
    esac
}

derive_cookie_domain() {
    local base_url="$1"
    local host
    host="${base_url#http://}"
    host="${host#https://}"
    host="${host%%/*}"
    host="${host%%:*}"
    case "$host" in
        localhost|127.*|0.0.0.0|::1)
            printf '\n'
            ;;
        *)
            printf '.%s\n' "$host"
            ;;
    esac
}

prompt_value() {
    local var_name="$1"
    local label="$2"
    local default_value="$3"
    local secret="${4:-0}"
    local input_value=""

    if [ -t 0 ]; then
        if [ "$secret" = "1" ]; then
            printf '%s [%s]: ' "$label" "$default_value"
            read -r -s input_value || true
            printf '\n'
        else
            printf '%s [%s]: ' "$label" "$default_value"
            read -r input_value || true
        fi
    fi

    if [ -n "$input_value" ]; then
        printf -v "$var_name" '%s' "$input_value"
    else
        printf -v "$var_name" '%s' "$default_value"
    fi
}

is_repo_root() {
    [ -f "$1/platform_config.py" ] && [ -f "$1/docker-compose.yml" ] && [ -f "$1/docker-compose.beta.yml" ]
}

ensure_source_tree() {
    if is_repo_root "$WORKDIR"; then
        return 0
    fi

    mkdir -p "$WORKDIR"
    if [ -n "$(find "$WORKDIR" -mindepth 1 -maxdepth 1 -print -quit 2>/dev/null || true)" ]; then
        warn "Extrahiere tt-infra in bestehendes Verzeichnis: $WORKDIR"
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

compose_files() {
    case "$PROFILE" in
        local) printf '%s\n' "-f" "docker-compose.yml" "-f" "docker-compose.local.yml" ;;
        beta) printf '%s\n' "-f" "docker-compose.beta.yml" ;;
        production) printf '%s\n' "-f" "docker-compose.prod.yml" ;;
        *) die "Unbekanntes Profil: $PROFILE" ;;
    esac
}

wait_for_postgres() {
    local timeout_seconds=180
    local deadline=$((SECONDS + timeout_seconds))

    info "Warte auf Postgres-Readiness ..."
    while [ "$SECONDS" -lt "$deadline" ]; do
        local container_id status
        container_id="$(cd "$WORKDIR" && docker compose --env-file "$ENV_FILE" "${COMPOSE_ARGS[@]}" ps -q tt-postgres 2>/dev/null || true)"
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

cleanup_on_error() {
    local exit_code=$?
    printf '\n' >&2
    warn "Setup fehlgeschlagen (Exit-Code ${exit_code})."
    if command -v docker >/dev/null 2>&1 && [ -f "$ENV_FILE" ]; then
        if docker compose version >/dev/null 2>&1; then
            warn "Aktueller Stack-Status:"
            (cd "$WORKDIR" && docker compose --env-file "$ENV_FILE" "${COMPOSE_ARGS[@]}" ps) >&2 || true
            warn "Letzte Postgres-Logs:"
            (cd "$WORKDIR" && docker compose --env-file "$ENV_FILE" "${COMPOSE_ARGS[@]}" logs --no-color --tail=80 tt-postgres) >&2 || true
        fi
    fi
    exit "$exit_code"
}

build_env_file() {
    local version="$1"
    local public_base_url="$2"
    local cookie_domain="$3"
    local project_name="$4"
    local admin_user="$5"
    local admin_pass="$6"

    local infra_secret auth_secret members_secret agenda_secret analytics_secret attendance_secret sso_shared_secret internal_api_secret
    local postgres_infra_password postgres_auth_password postgres_members_password postgres_agenda_password postgres_analytics_password postgres_attendance_password

    infra_secret="$(random_hex 64)"
    auth_secret="$(random_hex 64)"
    members_secret="$(random_hex 64)"
    agenda_secret="$(random_hex 64)"
    analytics_secret="$(random_hex 64)"
    attendance_secret="$(random_hex 64)"
    sso_shared_secret="$(random_hex 64)"
    internal_api_secret="$(random_hex 64)"

    postgres_infra_password="$(random_hex 32)"
    postgres_auth_password="$(random_hex 32)"
    postgres_members_password="$(random_hex 32)"
    postgres_agenda_password="$(random_hex 32)"
    postgres_analytics_password="$(random_hex 32)"
    postgres_attendance_password="$(random_hex 32)"

    local base_host
    base_host="${public_base_url#http://}"
    base_host="${base_host#https://}"
    base_host="${base_host%%/*}"

    local default_users="false"
    case "$PROFILE" in
        local|beta) default_users="true" ;;
    esac

    local db_suffix=""
    case "$PROFILE" in
        beta) db_suffix="_beta" ;;
    esac

    cat > "$ENV_FILE" <<EOF
COMPOSE_PROJECT_NAME=${project_name}
TZ=Europe/Zurich
LOG_LEVEL=INFO
GHCR_REGISTRY=ghcr.io
GHCR_OWNER=thun-tigers
TT_HOST_BIND_IP=172.17.0.1

PUBLIC_BASE_URL=${public_base_url}
AUTH_BASE_URL=${public_base_url}/auth
DEFAULT_MEMBERS_URL=${public_base_url}/members
DEFAULT_AGENDA_URL=${public_base_url}/agenda
DEFAULT_ANALYTICS_URL=${public_base_url}/analytics
DEFAULT_ATTENDANCE_URL=${public_base_url}/attendance
DEFAULT_INFRA_URL=${public_base_url}/infra
JWT_COOKIE_DOMAIN=${cookie_domain}
JWT_COOKIE_SECURE=true

TT_INFRA_IMAGE_TAG=v${version}
TT_AUTH_IMAGE_TAG=v${version}
TT_MEMBERS_IMAGE_TAG=v${version}
TT_AGENDA_IMAGE_TAG=v${version}
TT_ANALYTICS_IMAGE_TAG=v${version}
TT_ATTENDANCE_IMAGE_TAG=v${version}

INFRA_SECRET_KEY=${infra_secret}
AUTH_SECRET_KEY=${auth_secret}
MEMBERS_SECRET_KEY=${members_secret}
AGENDA_SECRET_KEY=${agenda_secret}
ANALYTICS_SECRET_KEY=${analytics_secret}
ATTENDANCE_SECRET_KEY=${attendance_secret}
SSO_SHARED_SECRET=${sso_shared_secret}
INTERNAL_API_SECRET=${internal_api_secret}

DEFAULT_ADMIN_USERNAME=${admin_user}
DEFAULT_ADMIN_PASSWORD=${admin_pass}
CREATE_DEFAULT_USERS=${default_users}
CREATE_DEFAULT_SERVICES=true
SSO_TOKEN_EXPIRY_SECONDS=60

INFRA_DATABASE_URL=postgresql+psycopg://tt_infra:${postgres_infra_password}@tt-postgres:5432/tt_infra${db_suffix}
AUTH_DATABASE_URL=postgresql+psycopg://tt_auth:${postgres_auth_password}@tt-postgres:5432/tt_auth${db_suffix}
MEMBERS_DATABASE_URL=postgresql+psycopg://tt_members:${postgres_members_password}@tt-postgres:5432/tt_members${db_suffix}
AGENDA_DATABASE_URL=postgresql+psycopg://tt_agenda:${postgres_agenda_password}@tt-postgres:5432/tt_agenda${db_suffix}
ANALYTICS_DATABASE_URL=postgresql+psycopg://tt_analytics:${postgres_analytics_password}@tt-postgres:5432/tt_analytics${db_suffix}
ATTENDANCE_DATABASE_URL=postgresql+psycopg://tt_attendance:${postgres_attendance_password}@tt-postgres:5432/tt_attendance${db_suffix}

POSTGRES_INFRA_PASSWORD=${postgres_infra_password}
POSTGRES_AUTH_PASSWORD=${postgres_auth_password}
POSTGRES_MEMBERS_PASSWORD=${postgres_members_password}
POSTGRES_AGENDA_PASSWORD=${postgres_agenda_password}
POSTGRES_ANALYTICS_PASSWORD=${postgres_analytics_password}
POSTGRES_ATTENDANCE_PASSWORD=${postgres_attendance_password}
EOF

    cp "$ENV_FILE" "$INSTANCE_DIR/generated.env"

    info "Env-Datei geschrieben: $ENV_FILE"
    info "Cookie-Domain: ${cookie_domain:-<leer>}"
    info "Projektname: $project_name"
    info "Base URL: $public_base_url"
    info "Postgres-Datenbank: tt-postgres"
}

parse_args() {
    while [ "$#" -gt 0 ]; do
        case "$1" in
            -h|--help)
                cat <<'EOF'
Verwendung:
  ./setup.sh [local|beta|production]
  ./setup.sh --profile <local|beta|production>

Das Skript fragt interaktiv nach Basis-URL und Admin-Daten und erzeugt
eine .env im aktuellen Verzeichnis.
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
ENV_FILE="$REPO_ROOT/.env"

if [ ! -f "$REPO_ROOT/VERSION" ]; then
    die "VERSION-Datei fehlt im aktuellen Verzeichnis: $REPO_ROOT"
fi
VERSION="$(tr -d '\n' < "$REPO_ROOT/VERSION")"

PROFILE="${PROFILE:-beta}"

case "$PROFILE" in
    local)
        default_base_url="http://localhost:8080"
        ;;
    beta)
        default_base_url="https://beta.thun-tigers.net"
        ;;
    production)
        default_base_url="https://thun-tigers.net"
        ;;
    *)
        die "Unbekanntes Profil: $PROFILE"
        ;;
esac

prompt_value PUBLIC_BASE_URL "Public Base URL oder Hostname" "$default_base_url" 0
PUBLIC_BASE_URL="$(normalize_base_url "$PUBLIC_BASE_URL")"

cookie_domain_default="$(derive_cookie_domain "$PUBLIC_BASE_URL")"
prompt_value COOKIE_DOMAIN_INPUT "JWT Cookie Domain" "$cookie_domain_default" 0
JWT_COOKIE_DOMAIN="${COOKIE_DOMAIN_INPUT:-$cookie_domain_default}"

default_project_name="$(basename "$WORKDIR" | tr '[:upper:]' '[:lower:]' | tr -cd 'a-z0-9_-')"
[ -n "$default_project_name" ] || default_project_name="tigers"
prompt_value COMPOSE_PROJECT_NAME "Compose Project Name" "$default_project_name" 0

prompt_value ADMIN_USERNAME "Admin Username" "admin" 0
prompt_value ADMIN_PASSWORD "Admin Password (leer = automatisch generiert)" "" 1
if [ -z "$ADMIN_PASSWORD" ]; then
    ADMIN_PASSWORD="$(random_hex 24)"
    info "Admin Password generiert: $ADMIN_PASSWORD"
fi

mkdir -p "$INSTANCE_DIR"

trap cleanup_on_error ERR

require_cmd docker
docker info >/dev/null 2>&1 || die "Docker-Daemon laeuft nicht oder ist nicht erreichbar."
docker compose version >/dev/null 2>&1 || die "Docker Compose ist nicht verfuegbar."

build_env_file "$VERSION" "$PUBLIC_BASE_URL" "$JWT_COOKIE_DOMAIN" "$COMPOSE_PROJECT_NAME" "$ADMIN_USERNAME" "$ADMIN_PASSWORD"

COMPOSE_ARGS=()
while IFS= read -r arg; do
    COMPOSE_ARGS+=("$arg")
done < <(compose_files)

info "Starte Stack ..."
cd "$REPO_ROOT"
docker compose --env-file "$ENV_FILE" "${COMPOSE_ARGS[@]}" up -d --build
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
        log "  Entry Point : ${PUBLIC_BASE_URL}"
        log "  Config-UI   : ${PUBLIC_BASE_URL}/infra/config"
        ;;
    production)
        log "  Entry Point : ${PUBLIC_BASE_URL}"
        log "  Config-UI   : ${PUBLIC_BASE_URL}/infra/config"
        ;;
esac
printf '\n'
log "Gespeicherte Konfiguration:"
log "  Verzeichnis : $REPO_ROOT"
log "  .env        : $ENV_FILE"
log "  instance    : $INSTANCE_DIR/generated.env"
printf '\n'
log "Initiale Login-Daten:"
log "  Benutzer    : $ADMIN_USERNAME"
log "  Passwort    : $ADMIN_PASSWORD"
