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


def test_admin_index_redirects_to_setup_when_unconfigured(client):
    _login_admin(client)

    response = client.get('/admin', follow_redirects=False)

    assert response.status_code == 302
    assert response.headers['Location'].endswith('/setup/') or response.headers['Location'].endswith('/setup')


def test_admin_index_no_longer_redirects_after_setup_save(client):
    _login_admin(client)

    response = client.post('/setup/', data={'DEPLOYMENT_NAME': 'tigers-local'}, follow_redirects=False)
    assert response.status_code == 302
    assert response.headers['Location'].rstrip('/').endswith('/config')

    response = client.get('/admin', follow_redirects=False)
    assert response.status_code == 200


def test_non_admin_session_is_not_redirected_to_setup(client):
    with client.session_transaction() as session:
        session['user_id'] = '2'
        session['username'] = 'member'
        session['service_role'] = 'user'
        session['platform_role'] = 'user'

    response = client.get('/admin', follow_redirects=False)

    assert response.status_code == 302
    assert '/setup' not in response.headers['Location']
