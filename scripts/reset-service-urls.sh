#!/usr/bin/env bash
# Emergency recovery: reset service URLs directly in tt-auth DB.
# Run this after a backup restore if the web UI is inaccessible.
#
# Usage:
#   ./scripts/reset-service-urls.sh              # local (localhost:8080)
#   ./scripts/reset-service-urls.sh beta         # beta  (beta.thun-tigers.net)
#
# The script reads DB credentials from the running tt-postgres container.

set -euo pipefail

PROFILE="${1:-local}"

if [[ "$PROFILE" == "beta" ]]; then
  BASE="https://beta.thun-tigers.net"
  MEMBERS_BASE="https://members-beta.thun-tigers.net"
else
  BASE="http://localhost:8080"
  MEMBERS_BASE="$BASE"
fi

MEMBERS_URL="${MEMBERS_BASE}/members"
AGENDA_URL="${BASE}/agenda"
ANALYTICS_URL="${BASE}/analytics"
INFRA_URL="${BASE}/infra"
ATTENDANCE_URL="${BASE}/attendance"

echo "Resetting service URLs for profile: $PROFILE"
echo "  members:    $MEMBERS_URL"
echo "  agenda:     $AGENDA_URL"
echo "  analytics:  $ANALYTICS_URL"
echo "  infra:      $INFRA_URL"
echo "  attendance: $ATTENDANCE_URL"
echo ""

SQL="
UPDATE service SET url = '$MEMBERS_URL'   WHERE name = 'members';
UPDATE service SET url = '$AGENDA_URL'    WHERE name = 'agenda';
UPDATE service SET url = '$ANALYTICS_URL' WHERE name = 'analytics';
UPDATE service SET url = '$INFRA_URL'     WHERE name = 'infra';
UPDATE service SET url = '$ATTENDANCE_URL' WHERE name = 'attendance';
UPDATE service SET internal_url = 'http://tt-members:5000'   WHERE name = 'members';
UPDATE service SET internal_url = 'http://tt-agenda:5000'    WHERE name = 'agenda';
UPDATE service SET internal_url = 'http://tt-analytics:5000' WHERE name = 'analytics';
UPDATE service SET internal_url = 'http://tt-infra:5000'     WHERE name = 'infra';
UPDATE service SET internal_url = 'http://tt-attendance:5000' WHERE name = 'attendance';
"

docker compose exec tt-postgres psql -U tt_auth -d tt_auth -c "$SQL"

echo ""
echo "Done. Restart the stack to apply: docker compose restart"
