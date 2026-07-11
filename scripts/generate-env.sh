#!/usr/bin/env bash
# Bootstrap-Skript: Erzeugt instance/generated.env ohne laufende Config-UI.
# Wird einmalig vor dem ersten "docker compose up" benötigt.
#
# Verwendung:
#   ./scripts/generate-env.sh [--version X.Y.Z] [local|beta|production]
#
# Danach:
#   docker compose --env-file ./instance/generated.env up -d --build
#
# Für beta/production müssen die Secrets zuerst in der Config-UI (/config)
# oder in den exportierten Laufzeitdateien unter instance/ gesetzt werden.

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

ENV_FILE="$REPO_ROOT/instance/generated.env"

echo "→ Generiere instance/generated.env für Profil '$PROFILE' ..."
ARGS=(generate --profile "$PROFILE")
if [ -n "$VERSION" ]; then
    ARGS+=(--version "$VERSION")
fi
"$PYTHON" "$SCRIPT_DIR/render_platform_env.py" "${ARGS[@]}"

echo ""
echo "Public URLs:"
for KEY in PUBLIC_BASE_URL AUTH_BASE_URL DEFAULT_MEMBERS_URL DEFAULT_AGENDA_URL \
           DEFAULT_ANALYTICS_URL DEFAULT_ATTENDANCE_URL DEFAULT_INFRA_URL; do
    VAL="$(grep "^${KEY}=" "$ENV_FILE" 2>/dev/null | cut -d= -f2-)"
    if [ -n "$VAL" ]; then
        printf "  %-28s %s\n" "${KEY}" "${VAL}"
    else
        printf "  %-28s (nicht gesetzt)\n" "${KEY}"
    fi
done
echo ""
if [ -n "$VERSION" ]; then
    echo "→ Bereit: docker compose --env-file ./instance/generated.env up -d --build"
else
    echo "→ Bereit: docker compose --env-file ./instance/generated.env up -d --build"
fi
