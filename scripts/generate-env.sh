#!/usr/bin/env bash
# Bootstrap-Skript: Erzeugt instance/generated.env ohne laufende Config-UI.
# Wird einmalig vor dem ersten "docker compose up" benötigt.
#
# Verwendung:
#   ./scripts/generate-env.sh [local|beta|production]
#
# Danach:
#   docker compose --env-file ./instance/generated.env up -d --build
#
# Für beta/production müssen die Secrets zuerst in der Config-UI (/config)
# oder direkt in instance/platform-config.json gesetzt werden.

set -euo pipefail

PROFILE="${1:-local}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

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
"$PYTHON" "$SCRIPT_DIR/render_platform_env.py" generate --profile "$PROFILE"

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
echo "→ Bereit: docker compose --env-file ./instance/generated.env up -d --build"
