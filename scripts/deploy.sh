#!/usr/bin/env bash
# Startet den Stack mit instance/generated.env.
# Erzeugt generated.env automatisch (local-Profil), falls noch nicht vorhanden.
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
ENV_FILE="$REPO_ROOT/instance/generated.env"

if [ ! -f "$ENV_FILE" ]; then
    echo "→ instance/generated.env nicht gefunden — erzeuge lokales Profil ..."
    "$SCRIPT_DIR/generate-env.sh" local
fi

echo "→ docker compose up -d $*"
cd "$REPO_ROOT"
docker compose --env-file ./instance/generated.env up -d "$@"
