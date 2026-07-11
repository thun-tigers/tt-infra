#!/usr/bin/env bash
# Erzeugt das interne instance/runtime.env mit Secrets und Ableitungen.
# Wird einmalig vor dem ersten "docker compose up" benötigt.
#
# Verwendung:
#   ./scripts/generate-env.sh [--version X.Y.Z] [local|beta|production]
#
# Danach:
#   docker compose --env-file .env --env-file ./instance/runtime.env -f compose.yml up -d
#
# Bedienbare Werte liegen in der minimalen Root-.env. Secrets werden beim
# ersten Lauf zufaellig erzeugt und bei spaeteren Renderings beibehalten.

set -euo pipefail

PROFILE="local"
VERSION=""
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

while [ "$#" -gt 0 ]; do
    case "$1" in
        --version)
            [ "$#" -ge 2 ] || { echo "ERROR: --version braucht ein Argument" >&2; exit 1; }
            VERSION="$2"
            shift 2
            ;;
        local|beta|production)
            PROFILE="$1"
            shift
            ;;
        -h|--help)
            echo "Verwendung: ./scripts/generate-env.sh [--version X.Y.Z] [local|beta|production]"
            exit 0
            ;;
        *)
            echo "ERROR: Unbekanntes Argument: $1" >&2
            exit 1
            ;;
    esac
done

if [ -z "$VERSION" ] && [ "$PROFILE" != "local" ] && [ -f "$REPO_ROOT/VERSION" ]; then
    VERSION="$(tr -d '\n' < "$REPO_ROOT/VERSION")"
fi

# Venv bevorzugen, falls vorhanden
if [ -f "$REPO_ROOT/.venv/bin/python" ]; then
    PYTHON="$REPO_ROOT/.venv/bin/python"
elif command -v python3 > /dev/null 2>&1; then
    PYTHON="python3"
else
    PYTHON="python"
fi

ENV_FILE="$REPO_ROOT/instance/runtime.env"
PROFILE_FILE="$REPO_ROOT/.env"

if [ -f "$PROFILE_FILE" ]; then
    set -a
    # shellcheck disable=SC1090
    . "$PROFILE_FILE"
    set +a
fi

echo "→ Generiere instance/runtime.env für Profil '$PROFILE' ..."
ARGS=(generate --profile "$PROFILE")
if [ -n "$VERSION" ]; then
    ARGS+=(--version "$VERSION")
fi
"$PYTHON" "$SCRIPT_DIR/render_platform_env.py" "${ARGS[@]}"

echo ""
echo "Public Entry Point: ${PUBLIC_BASE_URL}"
echo "Service-URLs werden in compose.yml daraus abgeleitet."
echo ""
if [ -n "$VERSION" ]; then
    echo "→ Bereit: docker compose --env-file .env --env-file ./instance/runtime.env -f compose.yml up -d"
else
    echo "→ Bereit: docker compose --env-file .env --env-file ./instance/runtime.env -f compose.yml up -d"
fi
