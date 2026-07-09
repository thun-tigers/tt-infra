import logging
import os
from pathlib import Path

from flask import Flask
from sqlalchemy import inspect, text
from werkzeug.middleware.proxy_fix import ProxyFix

from .config import Config
from .extensions import db
from .models import PositionGroup
from platform_config import detect_profile, load_profile_store, profile_values, save_profile_store


POSITION_GROUP_DEFAULTS = [
    {'key': 'OL', 'label': 'OL', 'sort_order': 1},
    {'key': 'DL', 'label': 'DL', 'sort_order': 2},
    {'key': 'LB', 'label': 'LB', 'sort_order': 3},
    {'key': 'RB', 'label': 'RB', 'sort_order': 4},
    {'key': 'DB', 'label': 'DB', 'sort_order': 5},
    {'key': 'TE', 'label': 'TE', 'sort_order': 6},
    {'key': 'WR', 'label': 'WR', 'sort_order': 7},
    {'key': 'QB', 'label': 'QB', 'sort_order': 8},
]


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    app.config['TT_CONFIG_PROFILE'] = detect_profile(os.environ)
    app.config['TT_CONFIG_STORE_PATH'] = str(Path(app.instance_path) / 'platform-config.json')

    log_level = getattr(logging, app.config.get('LOG_LEVEL', 'INFO').upper(), logging.INFO)
    formatter = logging.Formatter('[%(asctime)s +0000] [%(process)d] [%(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    root_logger = logging.getLogger()
    if not root_logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        root_logger.addHandler(handler)
    root_logger.setLevel(log_level)

    # Flask session config
    app.config.setdefault('SESSION_COOKIE_SECURE', True)
    app.config.setdefault('SESSION_COOKIE_HTTPONLY', True)
    app.config.setdefault('SESSION_COOKIE_SAMESITE', 'Lax')

    db.init_app(app)

    from .routes.api import bp as api_bp
    from .routes.auth import bp as auth_bp
    from .routes.admin import bp as admin_bp
    from .routes.config import bp as config_bp
    from .routes.backup import bp as backup_bp
    app.register_blueprint(api_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(config_bp)
    app.register_blueprint(backup_bp)

    # Zentrales UI-Layout aus tt-common
    from tt_common import register_shared_ui
    register_shared_ui(
        app,
        brand_label='Infra',
        brand_icon='bi-hdd-network',
        home_endpoint='admin.index',
        logout_endpoint='auth.logout',
    )

    @app.context_processor
    def inject_version():
        auth_base_url = app.config.get('AUTH_BASE_URL', 'http://localhost:8085').rstrip('/')
        return {
            'infra_service_name': 'tt-infra',
            'auth_base_url': auth_base_url,
            'auth_dashboard_url': f'{auth_base_url}/',
            # tt-infra ist ausschliesslich hinter tt-auth erreichbar und kennt
            # keinen eigenen Login-Zustand; das geteilte Layout gated aber auf
            # current_user, daher hier konstant gesetzt (Header immer sichtbar).
            'current_user': {
                'username': 'admin',
                'display_name': 'Admin',
                'role': 'admin',
                'platform_role': 'admin',
                'service_role': 'admin',
            },
            'pending_messages_count': 0,
        }

    with app.app_context():
        store_path = Path(app.config['TT_CONFIG_STORE_PATH'])
        store = load_profile_store(store_path)
        if not store_path.exists():
            save_profile_store(store_path, store)
        active_profile = app.config['TT_CONFIG_PROFILE']
        app.config.update(profile_values(active_profile, overrides=store.get(active_profile, {})))
        # Env vars for DB connections and critical paths always win over the profile store.
        # The store may contain empty-string placeholders (e.g. beta profile defaults) that
        # must not overwrite valid values injected by the container environment.
        _ENV_PRIORITY_KEYS = [
            'SQLALCHEMY_DATABASE_URI', 'DATABASE_URL',
            'AUTH_DATABASE_URL', 'MEMBERS_DATABASE_URL', 'AGENDA_DATABASE_URL',
            'ANALYTICS_DATABASE_URL', 'ATTENDANCE_DATABASE_URL',
            'AUTH_BASE_URL', 'PUBLIC_BASE_URL',
            'MEMBERS_INSTANCE_DIR', 'ANALYTICS_UPLOAD_ROOT',
            'SECRET_KEY', 'SSO_SHARED_SECRET', 'INTERNAL_API_SECRET',
        ]
        for _key in _ENV_PRIORITY_KEYS:
            _val = os.environ.get(_key)
            if _val:
                app.config[_key] = _val
        if app.config.get('AUTO_CREATE_DB', True):
            db.create_all()
            _ensure_schema()
            _seed_defaults()

        Path(app.config.get('MEMBERS_INSTANCE_DIR', '/backup-sources/tt-members-instance')).mkdir(parents=True, exist_ok=True)
        Path(app.config.get('ANALYTICS_UPLOAD_ROOT', '/backup-sources/tt-analytics-uploads')).mkdir(parents=True, exist_ok=True)

    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
    return app


def _ensure_schema():
    inspector = inspect(db.engine)
    if 'position_groups' not in inspector.get_table_names():
        return

    columns = {column['name'] for column in inspector.get_columns('position_groups')}
    dialect = db.engine.dialect.name
    bool_false = 'false' if dialect == 'postgresql' else '0'
    statements = []
    if 'sort_order' not in columns:
        statements.append('ALTER TABLE position_groups ADD COLUMN sort_order INTEGER NOT NULL DEFAULT 0')
    if 'is_active' not in columns:
        statements.append(f'ALTER TABLE position_groups ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT {bool_false}')
    for statement in statements:
        db.session.execute(text(statement))
    if statements:
        db.session.commit()


def _seed_defaults():
    changed = False
    existing = {row.key: row for row in PositionGroup.query.all()}
    for item in POSITION_GROUP_DEFAULTS:
        row = existing.get(item['key'])
        if not row:
            db.session.add(PositionGroup(**item))
            changed = True
            continue
        if not row.label:
            row.label = item['label']
            changed = True
        if row.sort_order in (None, 0):
            row.sort_order = item['sort_order']
            changed = True
        if row.is_active is None:
            row.is_active = True
            changed = True
    if changed:
        db.session.commit()
