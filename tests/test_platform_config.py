import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from platform_config import render_env, render_sections, release_manifest_sections, validate_profile


def test_local_env_render_includes_core_urls():
    rendered = render_env('local')
    assert 'COMPOSE_PROJECT_NAME=tigers-local' in rendered
    assert 'AUTH_BASE_URL=http://localhost:8080/auth' in rendered
    assert 'TT_INFRA_INTERNAL_URL=http://tt-infra:5000' in rendered
    assert 'DEFAULT_ATTENDANCE_INTERNAL_URL=http://tt-attendance:5000' in rendered
    assert 'MEMBERS_AUTH_BASE_URL=' not in rendered
    assert 'ANALYTICS_GEMINI_API_KEY=' in rendered


def test_beta_env_render_includes_image_tags():
    rendered = render_env('beta', version='0.1.8')
    assert 'COMPOSE_PROJECT_NAME=tigers-beta' in rendered
    assert 'TIGERS_VERSION=v0.1.8' in rendered
    assert 'JWT_COOKIE_DOMAIN=.thun-tigers.net' in rendered
    assert 'AUTH_BASE_URL=https://beta.thun-tigers.net' in rendered
    assert 'DEPLOYMENT_NAME=tigers-beta' in rendered
    assert 'CADDYFILE=Caddyfile.beta' in rendered


def test_release_manifest_render_matches_expected_tags():
    rendered = render_sections(release_manifest_sections('0.1.8'))
    assert rendered.count('TIGERS_VERSION=v0.1.8') == 1


def test_production_profile_validates():
    errors = validate_profile('production', version='0.1.8')
    assert errors == [
        'missing required value for INFRA_SECRET_KEY in Secrets',
        'missing required value for AUTH_SECRET_KEY in Secrets',
        'missing required value for MEMBERS_SECRET_KEY in Secrets',
        'missing required value for AGENDA_SECRET_KEY in Secrets',
        'missing required value for ANALYTICS_SECRET_KEY in Secrets',
        'missing required value for ATTENDANCE_SECRET_KEY in Secrets',
        'missing required value for SSO_SHARED_SECRET in Secrets',
        'missing required value for INTERNAL_API_SECRET in Secrets',
        'missing required value for POSTGRES_INFRA_PASSWORD in Postgres',
        'missing required value for POSTGRES_AUTH_PASSWORD in Postgres',
        'missing required value for POSTGRES_MEMBERS_PASSWORD in Postgres',
        'missing required value for POSTGRES_AGENDA_PASSWORD in Postgres',
        'missing required value for POSTGRES_ANALYTICS_PASSWORD in Postgres',
        'missing required value for POSTGRES_ATTENDANCE_PASSWORD in Postgres',
    ]
