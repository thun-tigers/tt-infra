from __future__ import annotations

from dataclasses import dataclass, replace
import json
import os
from pathlib import Path
from typing import Sequence


@dataclass(frozen=True)
class EnvEntry:
    key: str
    value: str
    required: bool = True


@dataclass(frozen=True)
class EnvSection:
    title: str
    entries: tuple[EnvEntry, ...]


def entry(key: str, value: str, required: bool = True) -> EnvEntry:
    return EnvEntry(key=key, value=value, required=required)


def section(title: str, *entries: EnvEntry) -> EnvSection:
    return EnvSection(title=title, entries=tuple(entries))


PROFILE_NAMES = ('local', 'beta', 'production')

# Keys derived at render time from PUBLIC_BASE_URL.
# They appear in generated.env for backwards compat but are NOT stored in
# platform-config.json and are NOT editable in the Config-UI.
PUBLIC_DERIVED_KEYS: frozenset[str] = frozenset({
    'AUTH_BASE_URL',
    'DEFAULT_MEMBERS_URL',
    'DEFAULT_AGENDA_URL',
    'DEFAULT_ANALYTICS_URL',
    'DEFAULT_INFRA_URL',
    'DEFAULT_ATTENDANCE_URL',
})


def _image_tag_entries(version: str) -> tuple[EnvEntry, ...]:
    tag = f'v{version.lstrip("v")}'
    return (
        entry('TT_INFRA_IMAGE_TAG', tag),
        entry('TT_AUTH_IMAGE_TAG', tag),
        entry('TT_MEMBERS_IMAGE_TAG', tag),
        entry('TT_AGENDA_IMAGE_TAG', tag),
        entry('TT_ANALYTICS_IMAGE_TAG', tag),
        entry('TT_ATTENDANCE_IMAGE_TAG', tag),
    )


def _release_manifest_sections(version: str) -> tuple[EnvSection, ...]:
    return (
        section(
            f'Platform release manifest: {version}',
            *_image_tag_entries(version),
        ),
    )


def render_sections(sections: Sequence[EnvSection]) -> str:
    lines: list[str] = []
    for idx, current in enumerate(sections):
        lines.append(f'# {current.title}')
        for item in current.entries:
            lines.append(f'{item.key}={item.value}')
        if idx != len(sections) - 1:
            lines.append('')
    return '\n'.join(lines) + '\n'


def merge_sections(sections: Sequence[EnvSection], overrides: dict[str, str] | None = None) -> tuple[EnvSection, ...]:
    if not overrides:
        return tuple(sections)
    merged_sections: list[EnvSection] = []
    for current in sections:
        merged_sections.append(
            EnvSection(
                title=current.title,
                entries=tuple(
                    replace(item, value=overrides.get(item.key, item.value))
                    for item in current.entries
                ),
            )
        )
    return tuple(merged_sections)


def flatten_sections(sections: Sequence[EnvSection]) -> dict[str, str]:
    flattened: dict[str, str] = {}
    for current in sections:
        for item in current.entries:
            flattened[item.key] = item.value
    return flattened


def validate_sections(sections: Sequence[EnvSection]) -> list[str]:
    errors: list[str] = []
    seen: dict[str, str] = {}
    for current in sections:
        for item in current.entries:
            previous = seen.get(item.key)
            if previous is not None:
                errors.append(f'duplicate key {item.key} in {previous} and {current.title}')
            else:
                seen[item.key] = current.title
            if item.required and item.value == '':
                errors.append(f'missing required value for {item.key} in {current.title}')
    return errors


def profile_sections(profile: str, version: str | None = None, include_image_tags: bool = False, overrides: dict[str, str] | None = None) -> tuple[EnvSection, ...]:
    if profile == 'local':
        sections = local_env_sections(version=version, include_image_tags=include_image_tags)
    elif profile == 'beta':
        sections = beta_env_sections(version or '0.1.15')
    elif profile == 'production':
        sections = production_env_sections(version or '0.1.0')
    else:
        raise ValueError(f'Unknown profile: {profile}')
    # User-store overrides applied first, then PUBLIC_BASE_URL derivation wins.
    merged = merge_sections(sections, overrides)
    return _apply_public_base_derivation(merged)


def profile_values(profile: str, version: str | None = None, include_image_tags: bool = False, overrides: dict[str, str] | None = None) -> dict[str, str]:
    return flatten_sections(profile_sections(profile, version=version, include_image_tags=include_image_tags, overrides=overrides))


def profile_validation_errors(profile: str, version: str | None = None, include_image_tags: bool = False, overrides: dict[str, str] | None = None) -> list[str]:
    return validate_sections(profile_sections(profile, version=version, include_image_tags=include_image_tags, overrides=overrides))


def _public_url_section(public_base_url: str) -> EnvSection:
    """Build the Public URLs section.

    PUBLIC_BASE_URL is the only editable entry; the six derived keys are
    placeholders overwritten at render time by _apply_public_base_derivation().
    """
    pub = public_base_url.rstrip('/')
    return section(
        'Public URLs',
        entry('PUBLIC_BASE_URL', pub),
        entry('AUTH_BASE_URL',         f'{pub}/auth'),
        entry('DEFAULT_MEMBERS_URL',   f'{pub}/members'),
        entry('DEFAULT_AGENDA_URL',    f'{pub}/agenda'),
        entry('DEFAULT_ANALYTICS_URL', f'{pub}/analytics'),
        entry('DEFAULT_INFRA_URL',     f'{pub}/infra'),
        entry('DEFAULT_ATTENDANCE_URL',f'{pub}/attendance'),
    )


def _apply_public_base_derivation(sections: tuple[EnvSection, ...]) -> tuple[EnvSection, ...]:
    """Recompute the six derived URL entries from PUBLIC_BASE_URL.

    Runs after merge_sections() so that any stored overrides for the derived
    keys are silently replaced. PUBLIC_BASE_URL always wins.
    """
    values = flatten_sections(sections)
    pub_base = values.get('PUBLIC_BASE_URL', '').rstrip('/')
    if not pub_base:
        return sections
    derived: dict[str, str] = {
        'AUTH_BASE_URL':         f'{pub_base}/auth',
        'DEFAULT_MEMBERS_URL':   f'{pub_base}/members',
        'DEFAULT_AGENDA_URL':    f'{pub_base}/agenda',
        'DEFAULT_ANALYTICS_URL': f'{pub_base}/analytics',
        'DEFAULT_INFRA_URL':     f'{pub_base}/infra',
        'DEFAULT_ATTENDANCE_URL':f'{pub_base}/attendance',
    }
    return merge_sections(sections, derived)


def _shared_secret_section(*, placeholders: bool) -> EnvSection:
    if placeholders:
        values = {
            'INFRA_SECRET_KEY': '',
            'AUTH_SECRET_KEY': '',
            'MEMBERS_SECRET_KEY': '',
            'AGENDA_SECRET_KEY': '',
            'ANALYTICS_SECRET_KEY': '',
            'ATTENDANCE_SECRET_KEY': '',
            'SSO_SHARED_SECRET': '',
            'INTERNAL_API_SECRET': '',
        }
    else:
        values = {
            'INFRA_SECRET_KEY': 'change-me-infra-secret',
            'AUTH_SECRET_KEY': 'change-me-auth-secret',
            'MEMBERS_SECRET_KEY': 'change-me-members-secret',
            'AGENDA_SECRET_KEY': 'change-me-agenda-secret',
            'ANALYTICS_SECRET_KEY': 'change-me-analytics-secret',
            'ATTENDANCE_SECRET_KEY': 'change-me-attendance-secret',
            'SSO_SHARED_SECRET': 'change-me-sso-shared-secret',
            'INTERNAL_API_SECRET': 'change-me-internal-api-secret',
        }
    return section('Secrets', *(entry(key, value, required=True) for key, value in values.items()))


def _internal_url_section() -> EnvSection:
    return section(
        'Internal URLs',
        entry('DEFAULT_MEMBERS_INTERNAL_URL', 'http://tt-members:5000'),
        entry('DEFAULT_AGENDA_INTERNAL_URL', 'http://tt-agenda:5000'),
        entry('DEFAULT_ANALYTICS_INTERNAL_URL', 'http://tt-analytics:5000'),
        entry('DEFAULT_INFRA_INTERNAL_URL', 'http://tt-infra:5000'),
        entry('DEFAULT_ATTENDANCE_INTERNAL_URL', 'http://tt-attendance:5000'),
        entry('TT_AUTH_INTERNAL_URL', 'http://tt-auth:5000'),
        entry('TT_MEMBERS_INTERNAL_URL', 'http://tt-members:5000'),
        entry('TT_AGENDA_INTERNAL_URL', 'http://tt-agenda:5000'),
        entry('TT_ANALYTICS_INTERNAL_URL', 'http://tt-analytics:5000'),
        entry('TT_ATTENDANCE_INTERNAL_URL', 'http://tt-attendance:5000'),
        entry('TT_INFRA_INTERNAL_URL', 'http://tt-infra:5000'),
    )


def local_env_sections(version: str | None = None, include_image_tags: bool = False) -> tuple[EnvSection, ...]:
    sections: list[EnvSection] = [
        section(
            'Core',
            entry('COMPOSE_PROJECT_NAME', 'tigers-local'),
            entry('TZ', 'Europe/Zurich'),
            entry('LOG_LEVEL', 'INFO'),
        ),
        _shared_secret_section(placeholders=False),
        _public_url_section('http://localhost:8080'),
        _internal_url_section(),
        section(
            'Infra',
            entry('INFRA_DATABASE_URL', 'postgresql+psycopg://tt_infra:tt_infra_password@tt-postgres:5432/tt_infra'),
            entry('MEMBERS_INSTANCE_DIR', '/backup-sources/tt-members-instance'),
            entry('ANALYTICS_UPLOAD_ROOT', '/backup-sources/tt-analytics-uploads'),
        ),
        section(
            'Auth',
            entry('AUTH_PORT', '8085'),
            entry('AUTH_DATABASE_URL', 'postgresql+psycopg://tt_auth:tt_auth_password@tt-postgres:5432/tt_auth'),
            entry('JWT_EXPIRY_HOURS', '8'),
            entry('JWT_COOKIE_DOMAIN', 'localhost'),
            entry('JWT_COOKIE_SECURE', 'false'),
            entry('SSO_TOKEN_EXPIRY_SECONDS', '60'),
            entry('CREATE_DEFAULT_USERS', 'true'),
            entry('CREATE_DEFAULT_SERVICES', 'true'),
            entry('DEFAULT_ADMIN_USERNAME', 'admin'),
            entry('DEFAULT_ADMIN_PASSWORD', 'admin'),
            entry('JWT_COOKIE_NAME', 'tt_jwt', required=False),
        ),
        section(
            'Members',
            entry('MEMBERS_PORT', '8088'),
            entry('MEMBERS_DATABASE_URL', 'postgresql+psycopg://tt_members:tt_members_password@tt-postgres:5432/tt_members'),
            entry('MEMBERS_SSO_EXPECTED_AUDIENCE', 'tt-members'),
        ),
        section(
            'Agenda',
            entry('AGENDA_PORT', '8086'),
            entry('AGENDA_DATABASE_URL', 'postgresql+psycopg://tt_agenda:tt_agenda_password@tt-postgres:5432/tt_agenda'),
            entry('AGENDA_WEBHOOK_ENABLED', 'false'),
            entry('AGENDA_WEBHOOK_URL', 'https://example.invalid/webhook', required=False),
            entry('AGENDA_SSO_EXPECTED_AUDIENCE', 'tt-agenda'),
            entry('AGENDA_SSO_AUTO_PROVISION_USERS', 'true'),
            entry('AGENDA_SSO_SYNC_ROLE', 'true'),
        ),
        section(
            'Analytics',
            entry('ANALYTICS_PORT', '8087'),
            entry('ANALYTICS_DATABASE_URL', 'postgresql+psycopg://tt_analytics:tt_analytics_password@tt-postgres:5432/tt_analytics'),
            entry('ANALYTICS_SSO_EXPECTED_AUDIENCE', 'tt-analytics'),
            entry('ANALYTICS_SSO_AUTO_PROVISION_USERS', 'true'),
            entry('ANALYTICS_SSO_SYNC_ROLE', 'true'),
            entry('ANALYTICS_MAX_CONTENT_LENGTH', '2147483648'),
            entry('ANALYTICS_GEMINI_API_KEY', '', required=False),
            entry('ANALYTICS_GEMINI_MODEL', 'gemini-2.5-flash'),
            entry('ANALYTICS_GEMINI_FILE_POLL_SECONDS', '5'),
            entry('ANALYTICS_GEMINI_FILE_POLL_TIMEOUT_SECONDS', '300'),
            entry('ANALYTICS_GEMINI_MAX_RETRIES', '8'),
            entry('ANALYTICS_GEMINI_RETRY_BUFFER_SECONDS', '5'),
            entry('ANALYTICS_GEMINI_RETRY_DEFAULT_SECONDS', '60'),
        ),
        section(
            'Attendance',
            entry('ATTENDANCE_PORT', '8089'),
            entry('ATTENDANCE_DATABASE_URL', 'postgresql+psycopg://tt_attendance:tt_attendance_password@tt-postgres:5432/tt_attendance'),
            entry('ATTENDANCE_SSO_EXPECTED_AUDIENCE', 'tt-attendance'),
        ),
        section(
            'Postgres',
            entry('POSTGRES_INFRA_DB', 'tt_infra'),
            entry('POSTGRES_INFRA_USER', 'tt_infra'),
            entry('POSTGRES_INFRA_PASSWORD', 'tt_infra_password'),
            entry('POSTGRES_AUTH_DB', 'tt_auth'),
            entry('POSTGRES_AUTH_USER', 'tt_auth'),
            entry('POSTGRES_AUTH_PASSWORD', 'tt_auth_password'),
            entry('POSTGRES_MEMBERS_DB', 'tt_members'),
            entry('POSTGRES_MEMBERS_USER', 'tt_members'),
            entry('POSTGRES_MEMBERS_PASSWORD', 'tt_members_password'),
            entry('POSTGRES_AGENDA_DB', 'tt_agenda'),
            entry('POSTGRES_AGENDA_USER', 'tt_agenda'),
            entry('POSTGRES_AGENDA_PASSWORD', 'tt_agenda_password'),
            entry('POSTGRES_ANALYTICS_DB', 'tt_analytics'),
            entry('POSTGRES_ANALYTICS_USER', 'tt_analytics'),
            entry('POSTGRES_ANALYTICS_PASSWORD', 'tt_analytics_password'),
            entry('POSTGRES_ATTENDANCE_DB', 'tt_attendance'),
            entry('POSTGRES_ATTENDANCE_USER', 'tt_attendance'),
            entry('POSTGRES_ATTENDANCE_PASSWORD', 'tt_attendance_password'),
        ),
        section('Redis', entry('REDIS_URL', 'redis://tt-redis:6379/0')),
    ]
    if include_image_tags and version:
        sections.insert(1, section('Images', *_image_tag_entries(version)))
    return tuple(sections)


def beta_env_sections(version: str) -> tuple[EnvSection, ...]:
    sections: list[EnvSection] = [
        section(
            'Core',
            entry('COMPOSE_PROJECT_NAME', 'tigers-beta'),
            entry('TZ', 'Europe/Zurich'),
            entry('LOG_LEVEL', 'INFO'),
            entry('GHCR_REGISTRY', 'ghcr.io'),
            entry('GHCR_OWNER', 'thun-tigers'),
            entry('TT_HOST_BIND_IP', '172.17.0.1'),
        ),
        section('Images', *_image_tag_entries(version)),
        _shared_secret_section(placeholders=False),
        _public_url_section('https://beta.thun-tigers.net'),
        _internal_url_section(),
        section(
            'Infra',
            entry('INFRA_DATABASE_URL', '', required=False),
            entry('MEMBERS_INSTANCE_DIR', '/backup-sources/tt-members-instance'),
            entry('ANALYTICS_UPLOAD_ROOT', '/backup-sources/tt-analytics-uploads'),
        ),
        section(
            'Auth',
            entry('AUTH_DATABASE_URL', '', required=False),
            entry('JWT_EXPIRY_HOURS', '8'),
            entry('JWT_COOKIE_DOMAIN', '.thun-tigers.net'),
            entry('JWT_COOKIE_SECURE', 'true'),
            entry('SSO_TOKEN_EXPIRY_SECONDS', '60'),
            entry('CREATE_DEFAULT_USERS', 'false'),
            entry('CREATE_DEFAULT_SERVICES', 'true'),
            entry('DEFAULT_ADMIN_USERNAME', 'admin'),
            entry('DEFAULT_ADMIN_PASSWORD', 'change-me-admin-password'),
        ),
        section(
            'Members',
            entry('MEMBERS_DATABASE_URL', '', required=False),
            entry('MEMBERS_SSO_EXPECTED_AUDIENCE', 'tt-members'),
        ),
        section(
            'Agenda',
            entry('AGENDA_DATABASE_URL', '', required=False),
            entry('AGENDA_WEBHOOK_ENABLED', 'false'),
            entry('AGENDA_WEBHOOK_URL', '', required=False),
            entry('AGENDA_SSO_EXPECTED_AUDIENCE', 'tt-agenda'),
            entry('AGENDA_SSO_AUTO_PROVISION_USERS', 'true'),
            entry('AGENDA_SSO_SYNC_ROLE', 'true'),
        ),
        section(
            'Analytics',
            entry('ANALYTICS_DATABASE_URL', '', required=False),
            entry('ANALYTICS_SSO_EXPECTED_AUDIENCE', 'tt-analytics'),
            entry('ANALYTICS_SSO_AUTO_PROVISION_USERS', 'true'),
            entry('ANALYTICS_SSO_SYNC_ROLE', 'true'),
            entry('ANALYTICS_MAX_CONTENT_LENGTH', '2147483648'),
            entry('ANALYTICS_GEMINI_API_KEY', '', required=False),
            entry('ANALYTICS_GEMINI_MODEL', 'gemini-2.5-flash'),
            entry('ANALYTICS_GEMINI_FILE_POLL_SECONDS', '5'),
            entry('ANALYTICS_GEMINI_FILE_POLL_TIMEOUT_SECONDS', '300'),
            entry('ANALYTICS_GEMINI_MAX_RETRIES', '8'),
            entry('ANALYTICS_GEMINI_RETRY_BUFFER_SECONDS', '5'),
            entry('ANALYTICS_GEMINI_RETRY_DEFAULT_SECONDS', '60'),
        ),
        section(
            'Attendance',
            entry('ATTENDANCE_DATABASE_URL', '', required=False),
            entry('ATTENDANCE_SSO_EXPECTED_AUDIENCE', 'tt-attendance'),
        ),
        section(
            'Postgres',
            entry('POSTGRES_INFRA_DB', 'tt_infra_beta'),
            entry('POSTGRES_INFRA_USER', 'tt_infra'),
            entry('POSTGRES_INFRA_PASSWORD', 'change-me-postgres-infra-password'),
            entry('POSTGRES_AUTH_DB', 'tt_auth_beta'),
            entry('POSTGRES_AUTH_USER', 'tt_auth'),
            entry('POSTGRES_AUTH_PASSWORD', 'change-me-postgres-auth-password'),
            entry('POSTGRES_MEMBERS_DB', 'tt_members_beta'),
            entry('POSTGRES_MEMBERS_USER', 'tt_members'),
            entry('POSTGRES_MEMBERS_PASSWORD', 'change-me-postgres-members-password'),
            entry('POSTGRES_AGENDA_DB', 'tt_agenda_beta'),
            entry('POSTGRES_AGENDA_USER', 'tt_agenda'),
            entry('POSTGRES_AGENDA_PASSWORD', 'change-me-postgres-agenda-password'),
            entry('POSTGRES_ANALYTICS_DB', 'tt_analytics_beta'),
            entry('POSTGRES_ANALYTICS_USER', 'tt_analytics'),
            entry('POSTGRES_ANALYTICS_PASSWORD', 'change-me-postgres-analytics-password'),
            entry('POSTGRES_ATTENDANCE_DB', 'tt_attendance_beta'),
            entry('POSTGRES_ATTENDANCE_USER', 'tt_attendance'),
            entry('POSTGRES_ATTENDANCE_PASSWORD', 'change-me-postgres-attendance-password'),
        ),
    ]
    return tuple(sections)


def production_env_sections(version: str) -> tuple[EnvSection, ...]:
    sections: list[EnvSection] = [
        section(
            'Core',
            entry('COMPOSE_PROJECT_NAME', 'tigers-production'),
            entry('TZ', 'Europe/Zurich'),
            entry('LOG_LEVEL', 'INFO'),
            entry('GHCR_REGISTRY', 'ghcr.io'),
            entry('GHCR_OWNER', 'thun-tigers'),
            entry('TT_HOST_BIND_IP', '172.17.0.1'),
        ),
        section('Images', *_image_tag_entries(version)),
        _shared_secret_section(placeholders=True),
        _public_url_section('https://thun-tigers.net'),
        _internal_url_section(),
        section(
            'Infra',
            entry('INFRA_DATABASE_URL', 'postgresql+psycopg://tt_infra:change-me@tt-postgres:5432/tt_infra'),
            entry('MEMBERS_INSTANCE_DIR', '/backup-sources/tt-members-instance'),
            entry('ANALYTICS_UPLOAD_ROOT', '/backup-sources/tt-analytics-uploads'),
        ),
        section(
            'Auth',
            entry('AUTH_DATABASE_URL', 'postgresql+psycopg://tt_auth:change-me@tt-postgres:5432/tt_auth'),
            entry('JWT_EXPIRY_HOURS', '8'),
            entry('JWT_COOKIE_DOMAIN', '.thun-tigers.net'),
            entry('JWT_COOKIE_SECURE', 'true'),
            entry('SSO_TOKEN_EXPIRY_SECONDS', '60'),
            entry('CREATE_DEFAULT_USERS', 'false'),
            entry('CREATE_DEFAULT_SERVICES', 'true'),
            entry('DEFAULT_ADMIN_USERNAME', 'admin'),
            entry('DEFAULT_ADMIN_PASSWORD', '', required=False),
        ),
        section(
            'Members',
            entry('MEMBERS_DATABASE_URL', 'postgresql+psycopg://tt_members:change-me@tt-postgres:5432/tt_members'),
            entry('MEMBERS_SSO_EXPECTED_AUDIENCE', 'tt-members'),
        ),
        section(
            'Agenda',
            entry('AGENDA_DATABASE_URL', 'postgresql+psycopg://tt_agenda:change-me@tt-postgres:5432/tt_agenda'),
            entry('AGENDA_WEBHOOK_ENABLED', 'false'),
            entry('AGENDA_WEBHOOK_URL', '', required=False),
            entry('AGENDA_SSO_EXPECTED_AUDIENCE', 'tt-agenda'),
            entry('AGENDA_SSO_AUTO_PROVISION_USERS', 'true'),
            entry('AGENDA_SSO_SYNC_ROLE', 'true'),
        ),
        section(
            'Analytics',
            entry('ANALYTICS_DATABASE_URL', 'postgresql+psycopg://tt_analytics:change-me@tt-postgres:5432/tt_analytics'),
            entry('ANALYTICS_SSO_EXPECTED_AUDIENCE', 'tt-analytics'),
            entry('ANALYTICS_SSO_AUTO_PROVISION_USERS', 'true'),
            entry('ANALYTICS_SSO_SYNC_ROLE', 'true'),
            entry('ANALYTICS_MAX_CONTENT_LENGTH', '2147483648'),
            entry('ANALYTICS_GEMINI_API_KEY', '', required=False),
            entry('ANALYTICS_GEMINI_MODEL', 'gemini-2.5-flash'),
            entry('ANALYTICS_GEMINI_FILE_POLL_SECONDS', '5'),
            entry('ANALYTICS_GEMINI_FILE_POLL_TIMEOUT_SECONDS', '300'),
            entry('ANALYTICS_GEMINI_MAX_RETRIES', '8'),
            entry('ANALYTICS_GEMINI_RETRY_BUFFER_SECONDS', '5'),
            entry('ANALYTICS_GEMINI_RETRY_DEFAULT_SECONDS', '60'),
        ),
        section(
            'Attendance',
            entry('ATTENDANCE_DATABASE_URL', 'postgresql+psycopg://tt_attendance:change-me@tt-postgres:5432/tt_attendance'),
            entry('ATTENDANCE_SSO_EXPECTED_AUDIENCE', 'tt-attendance'),
        ),
        section(
            'Postgres',
            entry('POSTGRES_INFRA_DB', 'tt_infra'),
            entry('POSTGRES_INFRA_USER', 'tt_infra'),
            entry('POSTGRES_INFRA_PASSWORD', ''),
            entry('POSTGRES_AUTH_DB', 'tt_auth'),
            entry('POSTGRES_AUTH_USER', 'tt_auth'),
            entry('POSTGRES_AUTH_PASSWORD', ''),
            entry('POSTGRES_MEMBERS_DB', 'tt_members'),
            entry('POSTGRES_MEMBERS_USER', 'tt_members'),
            entry('POSTGRES_MEMBERS_PASSWORD', ''),
            entry('POSTGRES_AGENDA_DB', 'tt_agenda'),
            entry('POSTGRES_AGENDA_USER', 'tt_agenda'),
            entry('POSTGRES_AGENDA_PASSWORD', ''),
            entry('POSTGRES_ANALYTICS_DB', 'tt_analytics'),
            entry('POSTGRES_ANALYTICS_USER', 'tt_analytics'),
            entry('POSTGRES_ANALYTICS_PASSWORD', ''),
            entry('POSTGRES_ATTENDANCE_DB', 'tt_attendance'),
            entry('POSTGRES_ATTENDANCE_USER', 'tt_attendance'),
            entry('POSTGRES_ATTENDANCE_PASSWORD', ''),
        ),
    ]
    return tuple(sections)


def release_manifest_sections(version: str) -> tuple[EnvSection, ...]:
    return _release_manifest_sections(version)


def render_env(profile: str, version: str | None = None, include_image_tags: bool | None = None) -> str:
    sections = profile_sections(profile, version=version, include_image_tags=bool(include_image_tags))
    return render_sections(sections)


def validate_profile(profile: str, version: str | None = None, include_image_tags: bool | None = None) -> list[str]:
    return profile_validation_errors(profile, version=version, include_image_tags=bool(include_image_tags))


def load_profile_store(path: Path, *, seed_defaults: bool = True) -> dict[str, dict[str, str]]:
    if path.exists():
        raw = json.loads(path.read_text(encoding='utf-8'))
    else:
        raw = {}

    store: dict[str, dict[str, str]] = {}
    for profile in PROFILE_NAMES:
        profile_data = raw.get(profile) if isinstance(raw, dict) else None
        if isinstance(profile_data, dict):
            store[profile] = {str(key): '' if value is None else str(value) for key, value in profile_data.items()}
        elif seed_defaults:
            store[profile] = profile_values(profile)
        else:
            store[profile] = {}
    return store


def save_profile_store(path: Path, store: dict[str, dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized = {
        profile: {str(key): '' if value is None else str(value) for key, value in values.items()}
        for profile, values in store.items()
    }
    path.write_text(json.dumps(normalized, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def detect_profile(environment: dict[str, str] | None = None) -> str:
    env = environment or os.environ
    explicit = (env.get('TT_CONFIG_PROFILE') or '').strip().lower()
    if explicit in PROFILE_NAMES:
        return explicit

    compose_name = (env.get('COMPOSE_PROJECT_NAME') or '').strip().lower()
    if 'beta' in compose_name:
        return 'beta'
    if 'production' in compose_name or 'prod' in compose_name:
        return 'production'
    return 'local'
