import json
import shutil
import sqlite3
import subprocess
import tarfile
import tempfile
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path

from flask import Blueprint, current_app, flash, redirect, render_template, request, send_file, session, url_for
from sqlalchemy.engine import make_url

bp = Blueprint('backup', __name__)


def _utc_timestamp():
    return datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')


def _sqlite_url_path(raw_url):
    if not raw_url:
        return None
    url = make_url(raw_url)
    if url.drivername.startswith('sqlite'):
        database = url.database or ''
        if database.startswith('/'):
            return Path(database)
        return Path(database).resolve()
    return None


def _postgres_dsn(raw_url):
    if not raw_url:
        return None
    url = make_url(raw_url)
    if not url.drivername.startswith('postgresql'):
        return None
    return url.set(drivername='postgresql').render_as_string(hide_password=False)


def _replace_directory_contents(target_dir, source_dir):
    target_path = Path(target_dir)
    source_path = Path(source_dir)
    target_path.mkdir(parents=True, exist_ok=True)
    for child in list(target_path.iterdir()):
        if child.is_dir() and not child.is_symlink():
            shutil.rmtree(child)
        else:
            child.unlink(missing_ok=True)
    for child in source_path.iterdir():
        destination = target_path / child.name
        if child.is_dir() and not child.is_symlink():
            shutil.copytree(child, destination)
        else:
            shutil.copy2(child, destination)


def _sqlite_backup_file(source_path, destination_path):
    source_path = Path(source_path)
    destination_path = Path(destination_path)
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(f'file:{source_path}?mode=ro', uri=True) as source_conn:
        with sqlite3.connect(destination_path) as dest_conn:
            source_conn.backup(dest_conn)


def _pg_dump_to_file(database_url, destination_path):
    dsn = _postgres_dsn(database_url)
    if not dsn:
        return False, 'Ungültige Postgres-URL.'

    destination_path = Path(destination_path)
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ['pg_dump', '--format=custom', '--no-owner', '--no-acl', '--file', str(destination_path), dsn],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return False, result.stderr.strip() or result.stdout.strip() or 'pg_dump fehlgeschlagen.'
    return True, None


def _pg_restore_from_file(database_url, archive_path):
    dsn = _postgres_dsn(database_url)
    if not dsn:
        return False, 'Ungültige Postgres-URL.'

    result = subprocess.run(
        ['pg_restore', '--clean', '--if-exists', '--no-owner', '--no-acl', '--dbname', dsn, str(archive_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return False, result.stderr.strip() or result.stdout.strip() or 'pg_restore fehlgeschlagen.'
    return True, None


def _backup_manifest():
    return {
        'format': 'tigers-stack-backup',
        'created_at': datetime.now(timezone.utc).isoformat(),
        'services': [],
    }


def _current_user():
    if not session.get('user_id'):
        return None
    return {
        'id': session.get('user_id'),
        'auth_user_id': session.get('auth_user_id'),
        'username': session.get('username'),
        'display_name': session.get('display_name') or session.get('username'),
        'service_role': session.get('service_role') or 'user',
        'platform_role': session.get('platform_role') or 'user',
        'permissions': session.get('permissions') or [],
        'role_permissions': session.get('role_permissions') or {},
        'memberships': session.get('memberships') or [],
        'claims_json': session.get('claims_json') or {},
    }


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user_id'):
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)

    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        current_user = _current_user()
        if not current_user:
            return redirect(url_for('auth.login'))
        if current_user.get('platform_role') != 'admin' and current_user.get('service_role') != 'admin':
            flash('Nur Administratoren haben Zugriff.', 'danger')
            return redirect(url_for('auth.login'))
        return f(*args, current_user=current_user, **kwargs)

    return decorated


def _build_backup_archive():
    timestamp = _utc_timestamp()
    workdir = Path(tempfile.mkdtemp(prefix='tt-infra-backup-'))
    payload_root = workdir / 'payload'
    payload_root.mkdir(parents=True, exist_ok=True)
    manifest = _backup_manifest()
    try:
        postgres_sources = [
            {'name': 'tt-infra', 'database_url': current_app.config.get('SQLALCHEMY_DATABASE_URI')},
            {'name': 'tt-members', 'database_url': current_app.config.get('MEMBERS_DATABASE_URL')},
            {'name': 'tt-auth', 'database_url': current_app.config.get('AUTH_DATABASE_URL')},
            {'name': 'tt-agenda', 'database_url': current_app.config.get('AGENDA_DATABASE_URL')},
            {'name': 'tt-attendance', 'database_url': current_app.config.get('ATTENDANCE_DATABASE_URL')},
            {'name': 'tt-analytics', 'database_url': current_app.config.get('ANALYTICS_DATABASE_URL')},
        ]

        members_upload_dir = Path(current_app.config.get('MEMBERS_INSTANCE_DIR', '/backup-sources/tt-members-instance')) / 'uploads'
        analytics_upload_dir = Path(current_app.config.get('ANALYTICS_UPLOAD_ROOT', '/backup-sources/tt-analytics-uploads'))

        members_upload_dir.mkdir(parents=True, exist_ok=True)

        infra_sqlite_source = _sqlite_url_path(current_app.config.get('SQLALCHEMY_DATABASE_URI'))
        if infra_sqlite_source:
            postgres_sources = [item for item in postgres_sources if item['name'] != 'tt-infra']
            sqlite_sources = [
                {
                    'name': 'tt-infra',
                    'kind': 'sqlite',
                    'source_file': infra_sqlite_source,
                },
            ]
        else:
            sqlite_sources = []

        file_sources = [
            {
                'name': 'tt-members-uploads',
                'kind': 'files',
                'source_dir': members_upload_dir,
            },
            {
                'name': 'tt-analytics-uploads',
                'kind': 'files',
                'source_dir': analytics_upload_dir,
            },
        ]

        for item in sqlite_sources:
            source_dir = item.get('source_dir')
            source_file = item.get('source_file')
            if source_file:
                if not source_file.exists():
                    raise RuntimeError(f"SQLite-Datenbank fehlt: {item['name']}")
                backup_path = payload_root / 'sqlite' / item['name'] / source_file.name
                _sqlite_backup_file(source_file, backup_path)
                manifest['services'].append({'name': item['name'], 'kind': 'sqlite', 'path': str(backup_path.relative_to(payload_root))})
                continue

            if not source_dir or not source_dir.exists():
                raise RuntimeError(f"Volume fehlt: {item['name']}")

            target_dir = payload_root / 'volumes' / item['name']
            shutil.copytree(source_dir, target_dir, dirs_exist_ok=True)
            manifest['services'].append({'name': item['name'], 'kind': 'files', 'path': str(target_dir.relative_to(payload_root))})

        for item in file_sources:
            source_dir = item.get('source_dir')
            if not source_dir or not source_dir.exists():
                raise RuntimeError(f"Volume fehlt: {item['name']}")

            target_dir = payload_root / 'volumes' / item['name']
            shutil.copytree(source_dir, target_dir, dirs_exist_ok=True)
            manifest['services'].append({'name': item['name'], 'kind': 'files', 'path': str(target_dir.relative_to(payload_root))})

        for item in postgres_sources:
            database_url = item.get('database_url')
            if not database_url:
                raise RuntimeError(f"Postgres-URL fehlt: {item['name']}")
            dump_path = payload_root / 'postgres' / f"{item['name']}.dump"
            ok, error = _pg_dump_to_file(database_url, dump_path)
            if not ok:
                raise RuntimeError(f"{item['name']}: {error}")
            manifest['services'].append({'name': item['name'], 'kind': 'postgres', 'path': str(dump_path.relative_to(payload_root))})

        manifest_path = payload_root / 'manifest.json'
        manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding='utf-8')

        archive_path = workdir / f'tigers_stack_backup_{timestamp}.tar.gz'
        with tarfile.open(archive_path, 'w:gz') as archive:
            archive.add(payload_root, arcname='payload')

        return archive_path, workdir, manifest
    except Exception:
        shutil.rmtree(workdir, ignore_errors=True)
        raise


def _restore_from_archive(archive_path):
    workdir = Path(tempfile.mkdtemp(prefix='tt-infra-restore-'))
    with tarfile.open(archive_path, 'r:gz') as archive:
        archive.extractall(workdir, filter='data')

    payload_root = workdir / 'payload'
    manifest_path = payload_root / 'manifest.json'
    if not manifest_path.exists():
        return False, 'Backup-Manifest fehlt.'

    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    if manifest.get('format') != 'tigers-stack-backup':
        return False, 'Unbekanntes Backup-Format.'

    members_dir = Path(current_app.config.get('MEMBERS_INSTANCE_DIR', '/backup-sources/tt-members-instance'))
    analytics_upload_dir = Path(current_app.config.get('ANALYTICS_UPLOAD_ROOT', '/backup-sources/tt-analytics-uploads'))
    infra_db_path = _sqlite_url_path(current_app.config.get('SQLALCHEMY_DATABASE_URI'))

    restore_results = []

    sqlite_restore_map = {
        'tt-infra': infra_db_path,
    }
    volume_restore_map = {
        'tt-members': members_dir,
        'tt-members-uploads': members_dir / 'uploads',
        'tt-analytics-uploads': analytics_upload_dir,
    }

    success = True

    for service in manifest.get('services', []):
        name = service.get('name')
        kind = service.get('kind')
        relative_path = service.get('path')
        if not name or not relative_path:
            continue
        source_path = payload_root / relative_path

        if kind == 'postgres':
            database_urls = {
                'tt-infra': current_app.config.get('SQLALCHEMY_DATABASE_URI'),
                'tt-members': current_app.config.get('MEMBERS_DATABASE_URL'),
                'tt-auth': current_app.config.get('AUTH_DATABASE_URL'),
                'tt-agenda': current_app.config.get('AGENDA_DATABASE_URL'),
                'tt-attendance': current_app.config.get('ATTENDANCE_DATABASE_URL'),
                'tt-analytics': current_app.config.get('ANALYTICS_DATABASE_URL'),
            }
            ok, error = _pg_restore_from_file(database_urls.get(name), source_path)
            if not ok:
                restore_results.append(f'{name}: {error}')
                success = False
            continue

        if kind == 'sqlite':
            target_path = sqlite_restore_map.get(name)
            if not target_path:
                success = False
                continue
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, target_path)
            restore_results.append(f'{name}: sqlite restored')
            continue

        if kind == 'volume':
            target_dir = volume_restore_map.get(name)
            if not target_dir:
                success = False
                continue
            _replace_directory_contents(target_dir, source_path)
            restore_results.append(f'{name}: volume restored')
            continue

        if kind == 'files':
            target_dir = volume_restore_map.get(name)
            if not target_dir:
                success = False
                continue
            _replace_directory_contents(target_dir, source_path)
            restore_results.append(f'{name}: files restored')

    if restore_results:
        current_app.logger.info('Backup restore completed: %s', '; '.join(restore_results))

    return success, restore_results


@bp.route('/backup')
@login_required
@admin_required
def backup_dashboard(current_user):
    return render_template(
        'backup.html',
        page_title='Backup & Restore',
        backup_root=str(Path(current_app.instance_path)),
        current_user=current_user,
        auth_logout_url=url_for('auth.logout'),
    )


@bp.route('/backup/download')
@login_required
@admin_required
def backup_download(current_user):
    try:
        archive_path, workdir, manifest = _build_backup_archive()
    except Exception as exc:
        current_app.logger.exception('Backup creation failed')
        flash(f'Backup fehlgeschlagen: {exc}', 'danger')
        return redirect(url_for('backup.backup_dashboard'))

    response = send_file(
        archive_path,
        as_attachment=True,
        download_name=archive_path.name,
        mimetype='application/gzip',
    )

    @response.call_on_close
    def _remove_temp():
        shutil.rmtree(workdir, ignore_errors=True)
    return response


@bp.route('/backup/restore', methods=['POST'])
@login_required
@admin_required
def backup_restore(current_user):
    upload = request.files.get('backup_file')
    if not upload or not upload.filename:
        flash('Bitte eine Backup-Datei auswählen.', 'danger')
        return redirect(url_for('backup.backup_dashboard'))

    confirm = (request.form.get('confirm_restore') or '').strip().lower()
    if confirm not in {'yes', 'ja', 'true', '1'}:
        flash('Bitte den Restore ausdrücklich bestätigen.', 'warning')
        return redirect(url_for('backup.backup_dashboard'))

    workdir = Path(tempfile.mkdtemp(prefix='tt-infra-restore-upload-'))
    archive_path = workdir / 'restore.tar.gz'
    upload.save(archive_path)

    try:
        ok, restore_results = _restore_from_archive(archive_path)
    except (tarfile.TarError, json.JSONDecodeError, OSError, sqlite3.Error, subprocess.SubprocessError) as exc:
        shutil.rmtree(workdir, ignore_errors=True)
        current_app.logger.exception('Restore failed')
        flash(f'Restore fehlgeschlagen: {exc}', 'danger')
        return redirect(url_for('backup.backup_dashboard'))

    shutil.rmtree(workdir, ignore_errors=True)

    if not ok:
        flash(f'Restore fehlgeschlagen: {"; ".join(restore_results) if isinstance(restore_results, list) else restore_results}', 'danger')
        return redirect(url_for('backup.backup_dashboard'))

    flash('Backup wiederhergestellt. Bitte die Services neu starten, damit alle Container die neuen Dateien und Datenbanken übernehmen.', 'success')
    return redirect(url_for('backup.backup_dashboard'))
