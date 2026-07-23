import re
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from platform_config import PROFILE_NAMES, PUBLIC_DERIVED_KEYS, profile_values

COMPOSE_VAR_RE = re.compile(r'\$\{([A-Z][A-Z0-9_]*)')

# Nicht ueber ${KEY} in compose.yml verdrahtet, aus dokumentierten Gruenden:
# - POSTGRES_*_DB: wird bewusst aus Servicename + ${DATABASE_SUFFIX} zusammengesetzt,
#   eine direkte Interpolation wuerde den Suffix doppelt anhaengen (siehe Kommentar
#   im tt-postgres-Block in compose.yml).
# - COMPOSE_PROJECT_NAME: reine docker-compose-CLI-Variable, nie als ${KEY} im
#   YAML-Body referenziert, sondern implizit von "docker compose" selbst aus der
#   .env gelesen.
# - TT_*_INTERNAL_URL / DEFAULT_*_INTERNAL_URL: Docker-interne DNS-Namen, die 1:1
#   den Servicenamen in compose.yml entsprechen (z.B. "tt-members" im Service-Key
#   UND im Hostnamen) - aendern sich nur, wenn compose.yml selbst umbenannt wird,
#   und muessten dann ohnehin dort mitgeaendert werden. Kein sinnvoll "editierbarer"
#   Wert.
# - *_PORT: nur fuer lokale Host-Port-Freigaben relevant, liegen in
#   docker-compose.local.yml statt compose.yml.
# - REDIS_URL: durch die granulareren RATELIMIT_STORAGE_URI/SSO_REPLAY_STORAGE_URI
#   pro Service ersetzt (mit eigener Redis-DB-Nummer je Service) - eigenstaendiger
#   Kandidat fuer eine spaetere Bereinigung aus dem Katalog, analog zu CADDYFILE.
NOT_COMPOSE_INTERPOLATED = {
    'POSTGRES_INFRA_DB', 'POSTGRES_AUTH_DB', 'POSTGRES_MEMBERS_DB',
    'POSTGRES_AGENDA_DB', 'POSTGRES_ATTENDANCE_DB', 'POSTGRES_ANALYTICS_DB',
    'COMPOSE_PROJECT_NAME',
    'TT_AUTH_INTERNAL_URL', 'TT_MEMBERS_INTERNAL_URL', 'TT_AGENDA_INTERNAL_URL',
    'TT_ANALYTICS_INTERNAL_URL', 'TT_ATTENDANCE_INTERNAL_URL', 'TT_INFRA_INTERNAL_URL',
    'DEFAULT_MEMBERS_INTERNAL_URL', 'DEFAULT_AGENDA_INTERNAL_URL',
    'DEFAULT_ANALYTICS_INTERNAL_URL', 'DEFAULT_ATTENDANCE_INTERNAL_URL',
    'DEFAULT_INFRA_INTERNAL_URL',
    'AUTH_PORT', 'MEMBERS_PORT', 'AGENDA_PORT', 'ANALYTICS_PORT', 'ATTENDANCE_PORT',
    'REDIS_URL',
}

# In compose.yml referenziert, aber keine platform_config.py-Katalogschluessel
# (docker-compose-eigene bzw. rein strukturelle Variablen).
# TIGERS_STACK_ROOT: interner Pfad fuer die Ops-Buttons (/ops/apply,
# /ops/restart), siehe app/config.py - kein vom Operator ueber die Config-UI
# editierbarer Wert, nur lokal ueberhaupt abweichend von seinem Default gesetzt.
MINIMAL_COMPOSE_KEYS = {'DEPLOYMENT_NAME', 'PUBLIC_BASE_URL', 'TIGERS_VERSION', 'DATABASE_SUFFIX', 'TIGERS_STACK_ROOT'}


def _compose_keys() -> set[str]:
    compose_path = project_root / 'compose.yml'
    text = compose_path.read_text(encoding='utf-8')
    return set(COMPOSE_VAR_RE.findall(text))


def _catalog_keys() -> set[str]:
    keys: set[str] = set()
    for profile in PROFILE_NAMES:
        keys |= set(profile_values(profile).keys())
    return keys


def test_every_compose_reference_is_a_known_key():
    compose_keys = _compose_keys()
    catalog_keys = _catalog_keys()
    unknown = compose_keys - catalog_keys - MINIMAL_COMPOSE_KEYS
    assert not unknown, f'compose.yml referenziert ${{{unknown}}}, aber platform_config.py kennt diese Schluessel nicht'


def test_every_editable_catalog_key_is_wired_in_compose():
    compose_keys = _compose_keys()
    catalog_keys = _catalog_keys()
    editable = catalog_keys - PUBLIC_DERIVED_KEYS - NOT_COMPOSE_INTERPOLATED
    missing = editable - compose_keys
    assert not missing, (
        f'platform_config.py definiert {missing} als editierbar, aber compose.yml '
        'referenziert diese Schluessel nirgends als ${VAR} - Aenderungen ueber '
        '/infra/config waeren fuer diese Felder wirkungslos'
    )
