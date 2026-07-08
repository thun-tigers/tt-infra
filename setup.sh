#!/usr/bin/env bash
# Einmaliger Setup-Befehl für eine neue Umgebung.
# Erzeugt instance/generated.env (local-Profil) und startet den Stack mit Rebuild.
#
# Verwendung:
#   ./setup.sh
#
# Für andere Profile:
#   ./scripts/generate-env.sh beta && ./scripts/deploy.sh --build

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== Tigers Stack Setup ==="
echo ""
"$SCRIPT_DIR/scripts/generate-env.sh" local
echo ""
"$SCRIPT_DIR/scripts/deploy.sh" --build
echo ""
echo "=== Setup abgeschlossen ==="
echo ""
echo "  Entry Point : http://localhost:8080"
echo "  Config-UI   : http://localhost:8080/infra/config"
echo ""
echo "Secrets und Passwörter jetzt in der Config-UI setzen."
