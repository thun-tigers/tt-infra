#!/usr/bin/env bash
# Startet den Stack mit minimaler .env und internem instance/runtime.env.
#
# Verwendung:
#   ./scripts/deploy.sh [docker-compose-flags...]
#
# Beispiele:
#   ./scripts/deploy.sh --build
#   ./scripts/deploy.sh --build tt-attendance tt-members
#   ./scripts/deploy.sh                    # nur (neu-)starten, kein Rebuild

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$REPO_ROOT/instance/runtime.env"

if [ ! -f "$ENV_FILE" ]; then
    echo "→ instance/runtime.env nicht gefunden — erzeuge lokales Profil ..."
    "$SCRIPT_DIR/generate-env.sh" local
fi

cd "$REPO_ROOT"

# DEPLOYMENT_NAME bestimmt die Namen von externem Netzwerk/Volume (siehe compose.yml).
# Default hier muss mit dem Default dort (${DEPLOYMENT_NAME:-tigers-beta}) uebereinstimmen.
DEPLOYMENT_NAME="tigers-beta"
if [ -f ./.env ]; then
    ENV_DEPLOYMENT_NAME="$(grep -E '^DEPLOYMENT_NAME=' ./.env | tail -n1 | cut -d= -f2-)"
    [ -n "$ENV_DEPLOYMENT_NAME" ] && DEPLOYMENT_NAME="$ENV_DEPLOYMENT_NAME"
fi

# compose.yml deklariert tigers-internal als externes Netzwerk — muss vor dem
# ersten "up" existieren, sonst bricht docker compose ab.
NETWORK_NAME="${DEPLOYMENT_NAME}-internal"
if ! docker network inspect "$NETWORK_NAME" > /dev/null 2>&1; then
    echo "→ externes Netzwerk '$NETWORK_NAME' fehlt — erzeuge es ..."
    docker network create "$NETWORK_NAME"
fi

COMPOSE_FILES=(-f compose.yml)
if [ -f docker-compose.local.yml ]; then
    COMPOSE_FILES+=(-f docker-compose.local.yml)

    # docker-compose.local.yml deklariert tt-members-data als externes Volume
    # (geteilt mit dem tt-members-Repo) — muss ebenfalls vorab existieren.
    MEMBERS_VOLUME="tt-members_tt-members-data"
    if ! docker volume inspect "$MEMBERS_VOLUME" > /dev/null 2>&1; then
        echo "→ externes Volume '$MEMBERS_VOLUME' fehlt — erzeuge es ..."
        docker volume create "$MEMBERS_VOLUME"
    fi
fi

echo "→ docker compose up -d $*"
docker compose --env-file ./.env --env-file ./instance/runtime.env "${COMPOSE_FILES[@]}" up -d "$@"
