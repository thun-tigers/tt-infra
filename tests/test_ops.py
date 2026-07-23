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


def _fake_run(returncodes):
    calls = []

    def fake(args, cwd, capture_output, text, timeout, check):
        calls.append(args)
        returncode = returncodes[len(calls) - 1]
        return type('Result', (), {'returncode': returncode, 'stdout': 'ok', 'stderr': ''})()

    return calls, fake


def test_apply_runs_generate_env_then_deploy_on_success(client, monkeypatch):
    _login_admin(client)
    calls, fake = _fake_run([0, 0])
    monkeypatch.setattr('app.routes.ops.subprocess.run', fake)

    response = client.post('/ops/apply', follow_redirects=False)

    assert response.status_code == 302
    assert response.headers['Location'].rstrip('/').endswith('/config')
    assert len(calls) == 2
    assert calls[0][:2] == ['bash', 'scripts/generate-env.sh']
    assert calls[1] == ['bash', 'scripts/deploy.sh']


def test_apply_stops_after_generate_env_failure(client, monkeypatch):
    _login_admin(client)
    calls, fake = _fake_run([1])
    monkeypatch.setattr('app.routes.ops.subprocess.run', fake)

    response = client.post('/ops/apply', follow_redirects=False)

    assert response.status_code == 302
    assert len(calls) == 1


def test_apply_reports_deploy_failure(client, monkeypatch):
    # Bewusst kein follow_redirects=True: das wuerde config.index rendern und
    # damit _load_store() aufrufen, was ausserhalb dieses Tests unerwuenschte
    # Seiteneffekte haette (Migration aus einer echten instance/-Datei, falls
    # Flasks Default-instance_path in Tests nicht isoliert ist).
    _login_admin(client)
    calls, fake = _fake_run([0, 1])
    monkeypatch.setattr('app.routes.ops.subprocess.run', fake)

    response = client.post('/ops/apply', follow_redirects=False)

    assert response.status_code == 302
    assert len(calls) == 2
    with client.session_transaction() as session:
        flashes = session.get('_flashes', [])
    assert any('fehlgeschlagen' in message for _category, message in flashes)


def test_restart_runs_only_deploy(client, monkeypatch):
    _login_admin(client)
    calls, fake = _fake_run([0])
    monkeypatch.setattr('app.routes.ops.subprocess.run', fake)

    response = client.post('/ops/restart', follow_redirects=False)

    assert response.status_code == 302
    assert response.headers['Location'].rstrip('/').endswith('/admin')
    assert calls == [['bash', 'scripts/deploy.sh']]


def test_apply_requires_admin_session(client, monkeypatch):
    calls, fake = _fake_run([0, 0])
    monkeypatch.setattr('app.routes.ops.subprocess.run', fake)

    response = client.post('/ops/apply', follow_redirects=False)

    assert response.status_code == 302
    assert '/login' in response.headers['Location']
    assert calls == []
