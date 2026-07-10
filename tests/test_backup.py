import io
import json
import sqlite3
import tarfile
from pathlib import Path

import jwt


def _prepare_sqlite_db(path, value):
    path = Path(path)
    if path.exists():
        path.unlink()
    conn = sqlite3.connect(path)
    try:
        conn.execute('CREATE TABLE demo (id INTEGER PRIMARY KEY, value TEXT NOT NULL)')
        conn.execute('INSERT INTO demo (value) VALUES (?)', (value,))
        conn.commit()
    finally:
        conn.close()


def _login_admin(client, app):
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


def test_admin_sso_login_sets_admin_session(client, app):
    token = jwt.encode(
        {
            'sub': '1',
            'username': 'admin',
            'service_role': 'admin',
            'platform_role': 'admin',
            'permissions': ['*'],
            'role_permissions': {},
            'memberships': [],
            'aud': 'tt-infra',
        },
        app.config.get('SSO_SHARED_SECRET') or app.config['SECRET_KEY'],
        algorithm='HS256',
    )

    response = client.get(f'/auth/sso?token={token}', follow_redirects=False)

    assert response.status_code == 302
    assert response.headers['Location'].endswith('/admin')
    with client.session_transaction() as session:
        assert session['username'] == 'admin'
        assert session['platform_role'] == 'admin'
        assert session['service_role'] == 'admin'


def test_backup_download_and_restore_roundtrip(client, app, monkeypatch, tmp_path):
    calls = []

    def fake_run(command, capture_output, text, check):
        calls.append(command)
        if command[0] == 'pg_dump':
            dump_path = Path(command[command.index('--file') + 1])
            dump_path.parent.mkdir(parents=True, exist_ok=True)
            dump_path.write_bytes(f'dump:{dump_path.stem}'.encode('utf-8'))
            return type('Result', (), {'returncode': 0, 'stdout': '', 'stderr': ''})()
        if command[0] == 'pg_restore':
            return type('Result', (), {'returncode': 0, 'stdout': '', 'stderr': ''})()
        raise AssertionError(f'Unexpected command: {command}')

    monkeypatch.setattr('app.routes.backup.subprocess.run', fake_run)
    _login_admin(client, app)
    members_dir = Path(app.config['MEMBERS_INSTANCE_DIR'])
    analytics_upload_root = Path(app.config['ANALYTICS_UPLOAD_ROOT'])
    infra_db_path = Path(app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', ''))

    _prepare_sqlite_db(infra_db_path, 'infra-before')
    members_dir.joinpath('uploads').mkdir(parents=True, exist_ok=True)
    members_dir.joinpath('uploads', 'license.txt').write_text('members-before', encoding='utf-8')
    analytics_upload_root.joinpath('clip.txt').write_text('analytics-before', encoding='utf-8')

    response = client.get('/backup/download')
    assert response.status_code == 200
    assert response.headers['Content-Type'].startswith('application/gzip')

    archive_bytes = io.BytesIO(response.data)
    with tarfile.open(fileobj=archive_bytes, mode='r:gz') as archive:
        manifest = json.loads(archive.extractfile('payload/manifest.json').read().decode('utf-8'))
        service_names = {service['name'] for service in manifest['services']}
        assert {'tt-infra', 'tt-members', 'tt-auth', 'tt-agenda', 'tt-attendance', 'tt-analytics', 'tt-members-uploads', 'tt-analytics-uploads'} <= service_names

    with sqlite3.connect(infra_db_path) as conn:
        conn.execute('UPDATE demo SET value = ?', ('infra-after',))
        conn.commit()
    members_dir.joinpath('uploads', 'license.txt').write_text('members-after', encoding='utf-8')
    analytics_upload_root.joinpath('clip.txt').write_text('analytics-after', encoding='utf-8')

    restore_file = tmp_path / 'restore.tar.gz'
    restore_file.write_bytes(response.data)

    with restore_file.open('rb') as handle:
        data = {'backup_file': (handle, 'restore.tar.gz'), 'confirm_restore': 'yes'}
        restore_response = client.post('/backup/restore', data=data, content_type='multipart/form-data')

    assert restore_response.status_code == 302
    assert any(command[0] == 'pg_restore' for command in calls)

    with sqlite3.connect(infra_db_path) as conn:
        value = conn.execute('SELECT value FROM demo').fetchone()[0]
        assert value == 'infra-before'
    assert members_dir.joinpath('uploads', 'license.txt').read_text(encoding='utf-8') == 'members-before'
    assert analytics_upload_root.joinpath('clip.txt').read_text(encoding='utf-8') == 'analytics-before'


def test_backup_restore_keeps_platform_config_store_unchanged(client, app, monkeypatch, tmp_path):
    calls = []

    def fake_run(command, capture_output, text, check):
        calls.append(command)
        if command[0] == 'pg_dump':
            dump_path = Path(command[command.index('--file') + 1])
            dump_path.parent.mkdir(parents=True, exist_ok=True)
            dump_path.write_bytes(f'dump:{dump_path.stem}'.encode('utf-8'))
            return type('Result', (), {'returncode': 0, 'stdout': '', 'stderr': ''})()
        if command[0] == 'pg_restore':
            return type('Result', (), {'returncode': 0, 'stdout': '', 'stderr': ''})()
        raise AssertionError(f'Unexpected command: {command}')

    monkeypatch.setattr('app.routes.backup.subprocess.run', fake_run)
    _login_admin(client, app)

    store_path = Path(app.config['TT_CONFIG_STORE_PATH'])
    store_path.parent.mkdir(parents=True, exist_ok=True)
    store_path.write_text(
        json.dumps({'local': {'PUBLIC_BASE_URL': 'https://current.example'}}, indent=2),
        encoding='utf-8',
    )

    response = client.get('/backup/download')
    assert response.status_code == 200

    store_path.write_text(
        json.dumps({'local': {'PUBLIC_BASE_URL': 'https://changed.example'}}, indent=2),
        encoding='utf-8',
    )

    restore_file = tmp_path / 'restore.tar.gz'
    restore_file.write_bytes(response.data)

    with restore_file.open('rb') as handle:
        data = {'backup_file': (handle, 'restore.tar.gz'), 'confirm_restore': 'yes'}
        restore_response = client.post('/backup/restore', data=data, content_type='multipart/form-data')

    assert restore_response.status_code == 302
    assert any(command[0] == 'pg_restore' for command in calls)
    assert json.loads(store_path.read_text(encoding='utf-8')) == {
        'local': {'PUBLIC_BASE_URL': 'https://changed.example'}
    }


def test_backup_restore_falls_back_when_pg_restore_hits_transaction_timeout(client, app, monkeypatch, tmp_path):
    calls = []

    def fake_run(command, capture_output, text, check, input=None):
        calls.append((command, input))
        if command[0] == 'pg_dump':
            dump_path = Path(command[command.index('--file') + 1])
            dump_path.parent.mkdir(parents=True, exist_ok=True)
            dump_path.write_bytes(b'dump:data')
            return type('Result', (), {'returncode': 0, 'stdout': '', 'stderr': ''})()
        if command[0] == 'pg_restore' and '--dbname' in command:
            return type(
                'Result',
                (),
                {
                    'returncode': 1,
                    'stdout': '',
                    'stderr': 'ERROR: unrecognized configuration parameter "transaction_timeout"',
                },
            )()
        if command[0] == 'pg_restore' and '--file' in command:
            return type('Result', (), {'returncode': 0, 'stdout': 'SET transaction_timeout = 0;\nSELECT 1;\n', 'stderr': ''})()
        if command[0] == 'psql':
            assert input == 'SELECT 1;\n'
            return type('Result', (), {'returncode': 0, 'stdout': '', 'stderr': ''})()
        raise AssertionError(f'Unexpected command: {command}')

    monkeypatch.setattr('app.routes.backup.subprocess.run', fake_run)
    _login_admin(client, app)

    members_dir = Path(app.config['MEMBERS_INSTANCE_DIR'])
    analytics_upload_root = Path(app.config['ANALYTICS_UPLOAD_ROOT'])
    infra_db_path = Path(app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', ''))

    _prepare_sqlite_db(infra_db_path, 'infra-before')
    members_dir.joinpath('uploads').mkdir(parents=True, exist_ok=True)
    analytics_upload_root.mkdir(parents=True, exist_ok=True)

    response = client.get('/backup/download')
    assert response.status_code == 200

    restore_file = tmp_path / 'restore.tar.gz'
    restore_file.write_bytes(response.data)

    with restore_file.open('rb') as handle:
        data = {'backup_file': (handle, 'restore.tar.gz'), 'confirm_restore': 'yes'}
        restore_response = client.post('/backup/restore', data=data, content_type='multipart/form-data')

    assert restore_response.status_code == 302
    assert any(command[0] == 'psql' for command, _ in calls)


def test_backup_download_fails_when_a_required_source_is_missing(client, app, monkeypatch):
    from app.routes import backup as backup_routes

    _login_admin(client, app)
    app.config['ANALYTICS_UPLOAD_ROOT'] = '/definitely/missing/uploads'

    response = client.get('/backup/download', follow_redirects=False)

    assert response.status_code == 302
    assert response.headers['Location'].endswith('/backup')
