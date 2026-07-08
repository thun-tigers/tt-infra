from __future__ import annotations

import os
from pathlib import Path

from flask import Blueprint, Response, abort, current_app, flash, redirect, render_template, request, url_for

from platform_config import (
    PROFILE_NAMES,
    load_profile_store,
    profile_sections,
    profile_values,
    profile_validation_errors,
    render_sections,
    release_manifest_sections,
    save_profile_store,
)

from .admin import admin_required

bp = Blueprint('config', __name__, url_prefix='/config')


SECRET_MARKERS = ('SECRET', 'PASSWORD', 'TOKEN', 'API_KEY')
BOOLEAN_HINTS = (
    '_ENABLED',
    '_SECURE',
    'AUTO_PROVISION',
    'SYNC_ROLE',
    'CREATE_DEFAULT_USERS',
    'CREATE_DEFAULT_SERVICES',
)
NUMBER_HINTS = (
    '_PORT',
    '_HOURS',
    '_SECONDS',
    '_RETRIES',
    'MAX_CONTENT_LENGTH',
)

TAB_DEFINITIONS = (
    ('routing', 'Routing', {'Core', 'Images', 'Secrets', 'Beta URLs', 'Production URLs', 'Public URLs', 'Internal URLs'}),
    ('infra', 'Infra', {'Infra'}),
    ('auth', 'Auth', {'Auth'}),
    ('members', 'Members', {'Members'}),
    ('agenda', 'Agenda', {'Agenda'}),
    ('analytics', 'Analytics', {'Analytics'}),
    ('attendance', 'Attendance', {'Attendance'}),
    ('data', 'Daten', {'Postgres', 'Redis'}),
)


def _store_path() -> Path:
    return Path(current_app.config['TT_CONFIG_STORE_PATH'])


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _active_profile() -> str:
    profile = (current_app.config.get('TT_CONFIG_PROFILE') or 'local').strip().lower()
    return profile if profile in PROFILE_NAMES else 'local'


def _release_version() -> str:
    version_file = _repo_root() / 'VERSION'
    return version_file.read_text(encoding='utf-8').strip()


def _is_secret(key: str) -> bool:
    return any(marker in key for marker in SECRET_MARKERS)


def _field_kind(key: str) -> str:
    if _is_secret(key):
        return 'password'
    if any(hint in key for hint in BOOLEAN_HINTS):
        return 'checkbox'
    if any(hint in key for hint in NUMBER_HINTS):
        return 'number'
    return 'text'


def _display_value(key: str, value: str) -> str:
    if not value:
        return 'Leer'
    if _is_secret(key):
        return 'Gespeichert'
    if value.lower() in {'true', 'false'}:
        return 'Ja' if value.lower() == 'true' else 'Nein'
    return value


def _profile_payload(profile: str, values: dict[str, str]) -> dict[str, object]:
    sections = profile_sections(profile, overrides=values)
    validation_errors = profile_validation_errors(profile, overrides=values)
    section_payloads = []
    for section in sections:
        entries = []
        for item in section.entries:
            entries.append(
                {
                    'key': item.key,
                    'value': item.value,
                    'display_value': _display_value(item.key, item.value),
                    'kind': _field_kind(item.key),
                    'required': item.required,
                    'masked': _is_secret(item.key),
                    'value_present': bool(item.value),
                }
            )
        section_payloads.append({'title': section.title, 'entries': entries})

    return {
        'name': profile,
        'sections': section_payloads,
        'validation_errors': validation_errors,
    }


def _build_tabs(sections: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped_sections: dict[str, list[dict[str, object]]] = {tab_key: [] for tab_key, _, _ in TAB_DEFINITIONS}
    for section in sections:
        title = str(section['title'])
        for tab_key, _, titles in TAB_DEFINITIONS:
            if title in titles:
                grouped_sections[tab_key].append(section)
                break
        else:
            grouped_sections.setdefault('routing', []).append(section)

    tabs: list[dict[str, object]] = []
    for tab_key, label, _ in TAB_DEFINITIONS:
        tabs.append(
            {
                'key': tab_key,
                'label': label,
                'sections': grouped_sections.get(tab_key, []),
            }
        )
    return tabs


def _load_store() -> dict[str, dict[str, str]]:
    return load_profile_store(_store_path())


def _save_store(store: dict[str, dict[str, str]]) -> None:
    save_profile_store(_store_path(), store)


def _restore_runtime_paths() -> None:
    if os.environ.get('MEMBERS_INSTANCE_DIR'):
        current_app.config['MEMBERS_INSTANCE_DIR'] = os.environ['MEMBERS_INSTANCE_DIR']
    if os.environ.get('ANALYTICS_UPLOAD_ROOT'):
        current_app.config['ANALYTICS_UPLOAD_ROOT'] = os.environ['ANALYTICS_UPLOAD_ROOT']


def _render_download(profile: str, values: dict[str, str], include_image_tags: bool = False, version: str | None = None) -> Response:
    rendered = render_sections(profile_sections(profile, version=version, include_image_tags=include_image_tags, overrides=values))
    if profile == 'local':
        filename = '.env.example'
    elif profile == 'beta':
        filename = '.env.arcane.beta'
    else:
        filename = '.env.portainer.production.example'
    return Response(
        rendered,
        mimetype='text/plain; charset=utf-8',
        headers={'Content-Disposition': f'attachment; filename={filename}'},
    )


def _parse_form(profile: str, current_values: dict[str, str]) -> dict[str, str]:
    result: dict[str, str] = dict(current_values)
    for section in profile_sections(profile):
        for item in section.entries:
            kind = _field_kind(item.key)
            if kind == 'checkbox':
                result[item.key] = 'true' if request.form.get(item.key) == 'on' else 'false'
                continue
            if kind == 'password':
                submitted = (request.form.get(item.key) or '').strip()
                if submitted:
                    result[item.key] = submitted
                elif item.key not in result:
                    result[item.key] = ''
                continue
            result[item.key] = (request.form.get(item.key) or '').strip()
    return result


@bp.route('', methods=['GET', 'POST'])
@bp.route('/', methods=['GET', 'POST'])
@bp.route('/<profile>', methods=['GET', 'POST'])
@admin_required
def index(current_user, profile: str | None = None):
    if profile:
        profile = (profile or '').strip().lower()
        if profile != _active_profile():
            abort(404)

    profile = _active_profile()
    active_tab = (request.values.get('tab') or 'routing').strip().lower()
    if active_tab not in {tab_key for tab_key, _, _ in TAB_DEFINITIONS}:
        active_tab = 'routing'
    store = _load_store()
    current_values = store.get(profile, {})

    if request.method == 'POST':
        updated_values = _parse_form(profile, current_values)
        store[profile] = updated_values
        _save_store(store)
        current_app.config.update(profile_values(profile, overrides=updated_values))
        _restore_runtime_paths()
        errors = profile_validation_errors(profile, overrides=updated_values)
        if errors:
            flash('Konfiguration gespeichert, aber es fehlen noch Pflichtwerte.', 'warning')
        else:
            flash('Konfiguration gespeichert.', 'success')
        return redirect(url_for('config.index', tab=active_tab))

    payload = _profile_payload(profile, current_values)
    tabs = _build_tabs(payload['sections'])
    return render_template(
        'config/index.html',
        page_title='Konfiguration – Tigers Platform',
        current_user=current_user,
        auth_login_url=url_for('auth.login'),
        auth_logout_url=url_for('auth.logout'),
        profile=profile,
        payload=payload,
        tabs=tabs,
        active_tab=active_tab,
        store_path=str(_store_path()),
        release_version=_release_version(),
        download_url=url_for('config.download_env'),
    )


@bp.route('/download')
@admin_required
def download_env(current_user):
    profile = _active_profile()
    store = _load_store()
    values = store.get(profile, {})
    include_image_tags = (request.args.get('include_image_tags') or '').strip().lower() in {'1', 'true', 'yes', 'y'}
    version = (request.args.get('version') or '').strip() or None
    if profile == 'local' and version:
        include_image_tags = True
    return _render_download(profile, values, include_image_tags=include_image_tags, version=version)


@bp.route('/releases/<version>/download')
@admin_required
def download_release_manifest(version, current_user):
    version = (version or '').strip()
    if not version:
        abort(404)
    rendered = render_sections(release_manifest_sections(version))
    return Response(
        rendered,
        mimetype='text/plain; charset=utf-8',
        headers={'Content-Disposition': f'attachment; filename=releases/{version}.env'},
    )
