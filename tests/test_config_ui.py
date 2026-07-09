import json
from pathlib import Path

from platform_config import profile_sections


def _login_admin(client):
    with client.session_transaction() as session:
        session['user_id'] = '1'
        session['auth_user_id'] = '1'
        session['username'] = 'admin'
        session['display_name'] = 'Admin'
        session['service_role'] = 'admin'
        session['platform_role'] = 'admin'
        session['permissions'] = ['*']
        session['role_permissions'] = {}
        session['memberships'] = []
        session['claims_json'] = {}


def _build_profile_form(profile_name, values):
    form = {}
    for section in profile_sections(profile_name):
        for item in section.entries:
            value = values.get(item.key, item.value)
            if item.key in {'CREATE_DEFAULT_USERS', 'CREATE_DEFAULT_SERVICES', 'JWT_COOKIE_SECURE', 'AGENDA_WEBHOOK_ENABLED', 'AGENDA_SSO_AUTO_PROVISION_USERS', 'AGENDA_SSO_SYNC_ROLE', 'ANALYTICS_SSO_AUTO_PROVISION_USERS', 'ANALYTICS_SSO_SYNC_ROLE'}:
                form[item.key] = 'on' if value == 'true' else ''
            elif item.key.endswith('_ENABLED') or item.key.endswith('_SECURE'):
                form[item.key] = 'on' if value == 'true' else ''
            elif item.key.endswith('_PASSWORD') or 'SECRET' in item.key or item.key.endswith('_TOKEN') or item.key.endswith('_API_KEY'):
                form[item.key] = value
            else:
                form[item.key] = value
    return form


def test_config_index_is_available(client):
    _login_admin(client)
    response = client.get('/config')
    assert response.status_code == 200
    assert b'Konfiguration' in response.data
    assert b'Aktive Umgebung' in response.data


def test_config_edit_persists_and_download_reflects_change(client, app):
    _login_admin(client)
    store_path = Path(app.config['TT_CONFIG_STORE_PATH'])
    store = json.loads(store_path.read_text(encoding='utf-8'))
    form = _build_profile_form('local', store['local'])
    form['LOG_LEVEL'] = 'DEBUG'

    response = client.post('/config', data=form, follow_redirects=False)
    assert response.status_code == 302

    updated_store = json.loads(store_path.read_text(encoding='utf-8'))
    assert updated_store['local']['LOG_LEVEL'] == 'DEBUG'
    assert app.config['LOG_LEVEL'] == 'DEBUG'

    download_response = client.get('/config/download')
    assert download_response.status_code == 200
    assert b'LOG_LEVEL=DEBUG' in download_response.data
