import json
import re
import urllib.error
import urllib.request

from flask import Blueprint, current_app, flash, jsonify, redirect, render_template, request, url_for

from ..extensions import db
from ..models import PositionGroup
from .admin import admin_required, login_required

bp = Blueprint('master_data', __name__, url_prefix='/stammdaten')

KEY_RE = re.compile(r'^[A-Z0-9_-]{1,40}$')


def _auth_base():
    return (
        current_app.config.get('TT_AUTH_INTERNAL_URL')
        or current_app.config.get('AUTH_BASE_URL', 'http://tt-auth:5000')
    ).rstrip('/')


def _agenda_base():
    return current_app.config.get('TT_AGENDA_INTERNAL_URL', 'http://tt-agenda:5000').rstrip('/')


def _auth_headers():
    secret = current_app.config.get('INTERNAL_API_SECRET')
    return {'X-TT-Internal-Secret': secret} if secret else {}


# ── Positionen (lokale DB) ──────────────────────────────────────────────────

@bp.route('/positionen')
@login_required
@admin_required
def positions(current_user):
    all_positions = PositionGroup.query.order_by(PositionGroup.sort_order, PositionGroup.label).all()
    return render_template('master_data_positions.html', current_user=current_user, positions=all_positions)


@bp.route('/positionen/new', methods=['POST'])
@login_required
@admin_required
def positions_new(current_user):
    key = (request.form.get('key') or '').strip().upper()
    label = (request.form.get('label') or '').strip()
    sort_order = int(request.form.get('sort_order') or 0)
    is_active = request.form.get('is_active') == 'y'

    if not key or not KEY_RE.match(key):
        flash('Ungültiger Schlüssel.', 'danger')
        return redirect(url_for('master_data.positions'))
    if not label:
        flash('Bezeichnung ist erforderlich.', 'danger')
        return redirect(url_for('master_data.positions'))
    if db.session.get(PositionGroup, key):
        flash('Der Schlüssel existiert bereits.', 'danger')
        return redirect(url_for('master_data.positions'))

    db.session.add(PositionGroup(key=key, label=label, sort_order=sort_order, is_active=is_active))
    db.session.commit()
    flash('Position gespeichert.', 'success')
    return redirect(url_for('master_data.positions'))


@bp.route('/positionen/<string:key>/edit', methods=['POST'])
@login_required
@admin_required
def positions_edit(current_user, key):
    normalized = (key or '').strip().upper()
    row = db.session.get(PositionGroup, normalized)
    if not row:
        if request.accept_mimetypes.accept_json and not request.accept_mimetypes.accept_html:
            return jsonify({'ok': False, 'error': 'Position nicht gefunden.'}), 404
        flash('Position nicht gefunden.', 'danger')
        return redirect(url_for('master_data.positions'))

    label = (request.form.get('label') or '').strip()
    sort_order = int(request.form.get('sort_order') or 0)
    is_active = request.form.get('is_active') == 'y'

    if not label:
        if request.accept_mimetypes.accept_json and not request.accept_mimetypes.accept_html:
            return jsonify({'ok': False, 'error': 'Bezeichnung ist erforderlich.'}), 400
        flash('Bezeichnung ist erforderlich.', 'danger')
        return redirect(url_for('master_data.positions'))

    row.label = label
    row.sort_order = sort_order
    row.is_active = is_active
    db.session.commit()

    if request.accept_mimetypes.accept_json and not request.accept_mimetypes.accept_html:
        return jsonify({'ok': True, 'label': label, 'is_active': is_active})
    flash('Position gespeichert.', 'success')
    return redirect(url_for('master_data.positions'))


@bp.route('/positionen/<string:key>/delete', methods=['POST'])
@login_required
@admin_required
def positions_delete(current_user, key):
    normalized = (key or '').strip().upper()
    row = db.session.get(PositionGroup, normalized)
    if not row:
        flash('Position nicht gefunden.', 'danger')
    else:
        db.session.delete(row)
        db.session.commit()
        flash('Position gelöscht.', 'success')
    return redirect(url_for('master_data.positions'))


@bp.route('/positionen/reorder', methods=['POST'])
@login_required
@admin_required
def positions_reorder(current_user):
    order = request.form.getlist('order')
    all_rows = PositionGroup.query.all()
    by_key = {row.key: row for row in all_rows}
    normalized = [k.strip().upper() for k in order if k.strip()]

    if len(normalized) != len(all_rows) or any(k not in by_key for k in normalized):
        flash('Ungültige Reihenfolge.', 'danger')
        return redirect(url_for('master_data.positions'))

    for idx, k in enumerate(normalized, start=1):
        by_key[k].sort_order = idx
    db.session.commit()
    flash('Reihenfolge gespeichert.', 'success')
    return redirect(url_for('master_data.positions'))


# ── Services (Proxy → tt-auth) ──────────────────────────────────────────────

def _auth_request(method, path, body=None):
    """HTTP call to tt-auth internal API using stdlib urllib."""
    url = f'{_auth_base()}{path}'
    data = json.dumps(body).encode() if body is not None else None
    headers = dict(_auth_headers())
    if data is not None:
        headers['Content-Type'] = 'application/json'
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=4) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        body_bytes = exc.read()
        try:
            payload = json.loads(body_bytes.decode())
        except Exception:
            payload = {}
        return exc.code, payload
    except urllib.error.URLError as exc:
        current_app.logger.warning('tt-auth request failed: %s %s – %s', method, path, exc)
        return None, {}


def _fetch_services():
    status, data = _auth_request('GET', '/api/internal/services')
    if status is None or status >= 400:
        return [], 'Services konnten nicht geladen werden.'
    return data.get('services', []), None


def _fetch_service(service_id):
    status, data = _auth_request('GET', f'/api/internal/services/{service_id}')
    if status is None:
        return None, 'Service konnte nicht geladen werden.'
    if status == 404:
        return None, 'Service nicht gefunden.'
    if status >= 400:
        return None, 'Service konnte nicht geladen werden.'
    return data.get('service'), None


@bp.route('/services')
@login_required
@admin_required
def services(current_user):
    svcs, error = _fetch_services()
    if error:
        flash(error, 'danger')
    return render_template('master_data_services.html', current_user=current_user, services=svcs)


@bp.route('/services/new', methods=['GET', 'POST'])
@login_required
@admin_required
def services_new(current_user):
    if request.method == 'POST':
        payload = _service_payload_from_form()
        status, _ = _auth_request('POST', '/api/internal/services', body=payload)
        if status is None:
            flash('Service konnte nicht erstellt werden.', 'danger')
            return render_template('master_data_service_form.html', current_user=current_user, action='Erstellen', form_data=payload)
        if status == 409:
            flash(f'Service "{payload["name"]}" existiert bereits.', 'danger')
            return render_template('master_data_service_form.html', current_user=current_user, action='Erstellen', form_data=payload)
        if status >= 400:
            flash('Service konnte nicht erstellt werden.', 'danger')
            return render_template('master_data_service_form.html', current_user=current_user, action='Erstellen', form_data=payload)
        flash(f'Service "{payload["name"]}" erstellt.', 'success')
        return redirect(url_for('master_data.services'))
    return render_template('master_data_service_form.html', current_user=current_user, action='Erstellen', form_data={})


@bp.route('/services/<int:service_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def services_edit(current_user, service_id):
    if request.method == 'POST':
        payload = _service_payload_from_form()
        status, _ = _auth_request('PUT', f'/api/internal/services/{service_id}', body=payload)
        if status is None:
            flash('Service konnte nicht gespeichert werden.', 'danger')
            return render_template('master_data_service_form.html', current_user=current_user, action='Bearbeiten', form_data=payload, service_id=service_id)
        if status == 409:
            flash(f'Service "{payload["name"]}" existiert bereits.', 'danger')
            return render_template('master_data_service_form.html', current_user=current_user, action='Bearbeiten', form_data=payload, service_id=service_id)
        if status >= 400:
            flash('Service konnte nicht gespeichert werden.', 'danger')
            return render_template('master_data_service_form.html', current_user=current_user, action='Bearbeiten', form_data=payload, service_id=service_id)
        flash(f'Service "{payload["name"]}" aktualisiert.', 'success')
        return redirect(url_for('master_data.services'))

    service, error = _fetch_service(service_id)
    if error:
        flash(error, 'danger')
        return redirect(url_for('master_data.services'))
    return render_template('master_data_service_form.html', current_user=current_user, action='Bearbeiten', form_data=service or {}, service_id=service_id)


@bp.route('/services/<int:service_id>/delete', methods=['POST'])
@login_required
@admin_required
def services_delete(current_user, service_id):
    service, _ = _fetch_service(service_id)
    status, _ = _auth_request('DELETE', f'/api/internal/services/{service_id}')
    if status is None or (status >= 400 and status != 404):
        flash('Service konnte nicht gelöscht werden.', 'danger')
    else:
        name = service.get('name') if service else str(service_id)
        flash(f'Service "{name}" gelöscht.', 'success')
    return redirect(url_for('master_data.services'))


def _service_payload_from_form():
    return {
        'name': (request.form.get('name') or '').strip(),
        'url': (request.form.get('url') or '').strip(),
        'internal_url': (request.form.get('internal_url') or '').strip() or None,
        'icon': (request.form.get('icon') or 'grid').strip(),
        'description': (request.form.get('description') or '').strip(),
        'required_role': request.form.get('required_role') or 'user',
        'is_active': request.form.get('is_active') == 'y',
        'sort_order': int(request.form.get('sort_order') or 0),
    }


# ── Trainingskategorien (Proxy → tt-agenda) ────────────────────────────────

def _agenda_request(method, path, body=None):
    """HTTP call to tt-agenda internal API."""
    url = f'{_agenda_base()}{path}'
    data = json.dumps(body).encode() if body is not None else None
    headers = dict(_auth_headers())
    if data is not None:
        headers['Content-Type'] = 'application/json'
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=4) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        body_bytes = exc.read()
        try:
            payload = json.loads(body_bytes.decode())
        except Exception:
            payload = {}
        return exc.code, payload
    except urllib.error.URLError as exc:
        current_app.logger.warning('tt-agenda request failed: %s %s – %s', method, path, exc)
        return None, {}


def _fetch_training_categories():
    status, data = _agenda_request('GET', '/api/internal/agenda-categories')
    if status is None or status >= 400:
        return [], 'Trainingskategorien konnten nicht geladen werden.'
    return data.get('categories', []), None


_AUDIENCE_OPTIONS = [
    ('player', 'Spieler'),
    ('coach', 'Betreuer / Coach'),
    ('team_manager', 'Teammanager'),
]


@bp.route('/trainingskategorien')
@login_required
@admin_required
def training_categories(current_user):
    cats, error = _fetch_training_categories()
    if error:
        flash(error, 'danger')
    return render_template(
        'master_data_training_categories.html',
        current_user=current_user,
        categories=cats,
        audience_options=_AUDIENCE_OPTIONS,
    )


@bp.route('/trainingskategorien/new', methods=['POST'])
@login_required
@admin_required
def training_categories_new(current_user):
    payload = _category_payload_from_form()
    status, data = _agenda_request('POST', '/api/internal/agenda-categories', body=payload)
    if status is None:
        flash('Kategorie konnte nicht erstellt werden.', 'danger')
    elif status == 409:
        flash(f'Schlüssel "{payload["key"]}" existiert bereits.', 'danger')
    elif status == 400:
        flash('Ungültiger Schlüssel oder fehlende Bezeichnung.', 'danger')
    elif status >= 400:
        flash('Kategorie konnte nicht erstellt werden.', 'danger')
    else:
        flash(f'Kategorie "{payload["label"]}" erstellt.', 'success')
    return redirect(url_for('master_data.training_categories'))


@bp.route('/trainingskategorien/<string:key>/edit', methods=['POST'])
@login_required
@admin_required
def training_categories_edit(current_user, key):
    payload = _category_payload_from_form()
    status, data = _agenda_request('PUT', f'/api/internal/agenda-categories/{key}', body=payload)
    if status is None:
        flash('Kategorie konnte nicht gespeichert werden.', 'danger')
    elif status == 404:
        flash('Kategorie nicht gefunden.', 'danger')
    elif status >= 400:
        flash('Kategorie konnte nicht gespeichert werden.', 'danger')
    else:
        flash(f'Kategorie "{payload["label"]}" gespeichert.', 'success')
    return redirect(url_for('master_data.training_categories'))


@bp.route('/trainingskategorien/<string:key>/delete', methods=['POST'])
@login_required
@admin_required
def training_categories_delete(current_user, key):
    status, data = _agenda_request('DELETE', f'/api/internal/agenda-categories/{key}')
    if status is None or (status >= 400 and status != 404):
        if data.get('error') == 'in_use':
            flash(f'Kategorie "{key}" wird noch von Trainings verwendet und kann nicht gelöscht werden.', 'danger')
        else:
            flash('Kategorie konnte nicht gelöscht werden.', 'danger')
    else:
        flash(f'Kategorie "{key}" gelöscht.', 'success')
    return redirect(url_for('master_data.training_categories'))


def _category_payload_from_form():
    return {
        'key': (request.form.get('key') or '').strip().lower(),
        'label': (request.form.get('label') or '').strip(),
        'icon': (request.form.get('icon') or 'bi-calendar-event').strip(),
        'badge_class': (request.form.get('badge_class') or '').strip(),
        'sort_order': int(request.form.get('sort_order') or 0),
        'active': request.form.get('active') == 'y',
        'attendance_required_for': request.form.getlist('attendance_required_for'),
        'attendance_allowed_for': request.form.getlist('attendance_allowed_for'),
        'show_presence_tracking': request.form.get('show_presence_tracking') == 'y',
    }
