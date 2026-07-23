from __future__ import annotations

import subprocess
from pathlib import Path

from flask import Blueprint, current_app, flash, redirect, url_for

from .admin import admin_required
from .config import _active_profile

bp = Blueprint('ops', __name__, url_prefix='/ops')


def _repo_root() -> Path:
    # Der live editierbare Host-Checkout (Docker-Socket + Repo als Bind-Mount,
    # siehe compose.yml/TIGERS_STACK_ROOT) - NICHT das Verzeichnis, in das das
    # Image gebaut wurde (/app): dort liegt nur ein zur Build-Zeit
    # eingefrorener Stand von scripts/ und compose.yml, nicht die aktuellen
    # .env/instance/runtime.env des Servers.
    return Path(current_app.config['TIGERS_STACK_ROOT'])


def _run(args: list[str], *, timeout: int) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            args,
            cwd=_repo_root(),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return False, f'Zeitüberschreitung nach {timeout}s bei: {" ".join(args)}'
    except OSError as exc:
        return False, f'Konnte nicht ausgeführt werden: {exc}'

    output = (result.stderr.strip() or result.stdout.strip())[-2000:]
    if result.returncode != 0:
        return False, output or f'{" ".join(args)} fehlgeschlagen (Exit-Code {result.returncode}).'
    return True, output


@bp.route('/apply', methods=['POST'])
@admin_required
def apply(current_user):
    profile = _active_profile()

    ok, message = _run(['bash', 'scripts/generate-env.sh', profile], timeout=60)
    if not ok:
        current_app.logger.error('generate-env.sh fehlgeschlagen: %s', message)
        flash(f'Übernehmen fehlgeschlagen (generate-env.sh): {message}', 'danger')
        return redirect(url_for('config.index'))

    ok, message = _run(['bash', 'scripts/deploy.sh'], timeout=300)
    if not ok:
        current_app.logger.error('deploy.sh fehlgeschlagen: %s', message)
        flash(f'Übernehmen fehlgeschlagen (deploy.sh): {message}', 'danger')
        return redirect(url_for('config.index'))

    flash('Konfiguration übernommen und Stack neu gestartet.', 'success')
    return redirect(url_for('config.index'))


@bp.route('/restart', methods=['POST'])
@admin_required
def restart(current_user):
    ok, message = _run(['bash', 'scripts/deploy.sh'], timeout=300)
    if not ok:
        current_app.logger.error('deploy.sh fehlgeschlagen: %s', message)
        flash(f'Neustart fehlgeschlagen: {message}', 'danger')
        return redirect(url_for('admin.index'))

    flash('Stack neu gestartet.', 'success')
    return redirect(url_for('admin.index'))
