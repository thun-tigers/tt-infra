from functools import wraps

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

bp = Blueprint('admin', __name__)


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user_id'):
            return redirect(url_for('auth.login', next=request.path))
        return f(*args, **kwargs)

    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        current_user = _current_user()
        if not current_user:
            return redirect(url_for('auth.login', next=request.path))
        if current_user.get('platform_role') != 'admin' and current_user.get('service_role') != 'admin':
            flash('Nur Administratoren haben Zugriff.', 'danger')
            return redirect(url_for('auth.login'))
        return f(*args, current_user=current_user, **kwargs)

    return decorated


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


@bp.route('/')
@bp.route('/admin')
@login_required
@admin_required
def index(current_user):
    return render_template(
        'admin.html',
        page_title='Admin – Tigers Platform',
        current_user=current_user,
        auth_login_url=url_for('auth.login'),
        auth_logout_url=url_for('auth.logout'),
    )
