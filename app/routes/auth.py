import secrets
from urllib.parse import urlencode, urljoin, urlparse

import jwt
from flask import Blueprint, current_app, flash, redirect, request, session, url_for

bp = Blueprint('auth', __name__)


def is_safe_url(target):
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ('http', 'https') and ref_url.netloc == test_url.netloc


def get_auth_login_url(next_page=None):
    auth_base_url = current_app.config.get('AUTH_BASE_URL', 'http://localhost:8085').rstrip('/')
    query = {'next_service': 'tt-infra'}
    if next_page:
        query['next'] = next_page
    return f"{auth_base_url}/?{urlencode(query)}"


def get_auth_logout_url():
    auth_base_url = current_app.config.get('AUTH_BASE_URL', 'http://localhost:8085').rstrip('/')
    return f'{auth_base_url}/logout'


def _store_session(payload):
    claims = payload.get('claims') or {}
    session['user_id'] = payload.get('sub')
    session['auth_user_id'] = payload.get('sub')
    session['username'] = claims.get('username') or payload.get('username')
    session['display_name'] = claims.get('display_name') or claims.get('username') or payload.get('username')
    session['service_role'] = payload.get('service_role') or payload.get('role') or 'user'
    session['platform_role'] = payload.get('platform_role') or payload.get('role') or 'user'
    session['permissions'] = payload.get('permissions') or []
    session['role_permissions'] = payload.get('role_permissions') or {}
    session['memberships'] = payload.get('memberships') or []
    session['claims_json'] = claims
    session['nonce'] = secrets.token_hex(8)


@bp.route('/login')
def login():
    return redirect(get_auth_login_url(request.args.get('next')))


@bp.route('/logout', methods=['GET', 'POST'])
def logout():
    session.clear()
    return redirect(get_auth_logout_url())


@bp.route('/auth/sso')
def sso_login():
    token = (request.args.get('token') or '').strip()
    if not token:
        flash('SSO-Token fehlt.', 'danger')
        return redirect(url_for('auth.login'))

    try:
        payload = jwt.decode(
            token,
            current_app.config.get('SSO_SHARED_SECRET') or current_app.config.get('SECRET_KEY'),
            algorithms=['HS256'],
            audience=current_app.config.get('SSO_EXPECTED_AUDIENCE', 'tt-infra'),
        )
    except jwt.ExpiredSignatureError:
        flash('SSO-Token ist abgelaufen. Bitte erneut starten.', 'warning')
        return redirect(url_for('auth.login'))
    except jwt.InvalidTokenError:
        flash('Ungültiger SSO-Token.', 'danger')
        return redirect(url_for('auth.login'))

    username = ((payload.get('claims') or {}).get('username') or payload.get('username') or '').strip()
    if not username:
        flash('SSO-Token enthält keinen Benutzernamen.', 'danger')
        return redirect(url_for('auth.login'))

    _store_session(payload)

    next_page = request.args.get('next')
    if next_page and is_safe_url(next_page):
        return redirect(next_page)
    return redirect(url_for('admin.index'))
