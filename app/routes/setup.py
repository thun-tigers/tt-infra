from __future__ import annotations

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for

from config_store import load_profile_overrides_from_db
from platform_config import infer_field_kind, profile_sections, profile_values

from .admin import admin_required
from .config import _active_profile, _load_store, _save_store, _write_generated_env
from ..extensions import db

bp = Blueprint('setup', __name__, url_prefix='/setup')


# Nur Werte, die vor dem produktiven Einsatz einmalig sinnvoll gesetzt werden -
# keine Secrets (die generiert render_platform_env.py bereits automatisch) und
# keine Admin-Zugangsdaten (die kommen zwingend aus .env vor dem allerersten
# Deploy, siehe docs/CONFIG_UI_AND_RUNTIME_ENV.md - ein bereits eingeloggter
# Admin kann sein eigenes Login hier nicht rueckwirkend aendern).
WIZARD_KEYS = (
    'PUBLIC_BASE_URL',
    'DEPLOYMENT_NAME',
    'AGENDA_WEBHOOK_ENABLED',
    'AGENDA_WEBHOOK_URL',
    'ANALYTICS_GEMINI_API_KEY',
)


def _wizard_entries(profile: str, values: dict[str, str]) -> list[dict[str, object]]:
    by_key = {}
    for section in profile_sections(profile, overrides=values):
        for item in section.entries:
            by_key[item.key] = item
    entries = []
    for key in WIZARD_KEYS:
        item = by_key.get(key)
        if item is None:
            continue
        entries.append({
            'key': item.key,
            'value': item.value,
            'kind': infer_field_kind(item.key),
        })
    return entries


@bp.route('', methods=['GET', 'POST'])
@bp.route('/', methods=['GET', 'POST'])
@admin_required
def index(current_user):
    profile = _active_profile()

    if request.method == 'POST':
        # Bewusst sparsam: Basis sind die tatsaechlich schon gespeicherten
        # Overrides je Profil (meist keine, bei einem Erstdeploy) plus die
        # Wizard-Felder fuer das aktive Profil - NICHT die volle, mit Defaults
        # gemergte Sicht aus _load_store(). Sonst wuerden beim allerersten
        # Speichern alle 90+ Katalog-Werte (auch fuer die anderen beiden
        # Profile!) als "explizit gesetzt" eingefroren, und spaetere
        # Verbesserungen an einem Default in platform_config.py wuerden nie
        # mehr durchschlagen (siehe config_store.py::load_profile_store_from_db).
        store = load_profile_overrides_from_db(db.engine)
        updates = dict(store.get(profile, {}))
        for key in WIZARD_KEYS:
            kind = infer_field_kind(key)
            if kind == 'checkbox':
                updates[key] = 'true' if request.form.get(key) == 'on' else 'false'
            else:
                submitted = (request.form.get(key) or '').strip()
                if submitted:
                    updates[key] = submitted

        store[profile] = updates
        _save_store(store)
        current_app.config.update(profile_values(profile, overrides=updates))
        try:
            _write_generated_env(profile, updates)
        except OSError as exc:
            current_app.logger.error('Fehler beim Schreiben von generated.env: %s', exc)

        flash(
            'Ersteinrichtung gespeichert. Wirksam erst nach "Übernehmen & Neustarten" auf der '
            'Konfigurationsseite. Weitere Einstellungen findest du dort jederzeit.',
            'success',
        )
        return redirect(url_for('config.index'))

    current_values = _load_store().get(profile, {})
    entries = _wizard_entries(profile, current_values)
    return render_template(
        'setup/index.html',
        page_title='Ersteinrichtung – Tigers Platform',
        current_user=current_user,
        auth_login_url=url_for('auth.login'),
        auth_logout_url=url_for('auth.logout'),
        profile=profile,
        entries=entries,
    )
