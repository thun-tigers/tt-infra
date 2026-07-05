import logging
import os
from pathlib import Path

from flask import Flask
from sqlalchemy import inspect, text

from .config import Config
from .extensions import db
from .models import PositionGroup


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

    log_level = getattr(logging, app.config.get('LOG_LEVEL', 'INFO').upper(), logging.INFO)
    logging.basicConfig(level=log_level)

    db.init_app(app)

    from .routes.api import bp as api_bp
    from .routes.auth import bp as auth_bp
    from .routes.admin import bp as admin_bp
    from .routes.backup import bp as backup_bp
    app.register_blueprint(api_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(backup_bp)

    @app.context_processor
    def inject_version():
        return {'infra_service_name': 'tt-infra'}

    with app.app_context():
        if app.config.get('AUTO_CREATE_DB', True):
            db.create_all()
            _ensure_schema()
            _seed_defaults()

        Path(app.config.get('MEMBERS_INSTANCE_DIR', '/backup-sources/tt-members-instance')).mkdir(parents=True, exist_ok=True)
        Path(app.config.get('ANALYTICS_UPLOAD_ROOT', '/backup-sources/tt-analytics-uploads')).mkdir(parents=True, exist_ok=True)

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
