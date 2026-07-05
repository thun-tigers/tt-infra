import os
import sys
from pathlib import Path

import pytest


@pytest.fixture()
def app(tmp_path):
    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    infra_instance = tmp_path / 'infra-instance'
    members_instance = tmp_path / 'members-instance'
    analytics_uploads = tmp_path / 'analytics-uploads'
    infra_instance.mkdir()
    members_instance.mkdir()
    analytics_uploads.mkdir()

    os.environ.setdefault('SECRET_KEY', 'test-secret')
    os.environ.setdefault('SQLALCHEMY_DATABASE_URI', f'sqlite:///{infra_instance / "infra.db"}')
    os.environ.setdefault('AUTO_CREATE_DB', 'true')
    os.environ.setdefault('INTERNAL_API_SECRET', 'test-internal-secret')
    os.environ.setdefault('MEMBERS_DATABASE_URL', 'postgresql+psycopg://tt_members:tt_members_password@tt-postgres-members:5432/tt_members')
    os.environ.setdefault('AUTH_DATABASE_URL', 'postgresql+psycopg://tt_auth:tt_auth_password@tt-postgres-auth:5432/tt_auth')
    os.environ.setdefault('AGENDA_DATABASE_URL', 'postgresql+psycopg://tt_agenda:tt_agenda_password@tt-postgres-agenda:5432/tt_agenda')
    os.environ.setdefault('ATTENDANCE_DATABASE_URL', 'postgresql+psycopg://tt_attendance:tt_attendance_password@tt-postgres-attendance:5432/tt_attendance')
    os.environ.setdefault('ANALYTICS_DATABASE_URL', 'postgresql+psycopg://tt_analytics:tt_analytics_password@tt-postgres-analytics:5432/tt_analytics')
    os.environ.setdefault('MEMBERS_INSTANCE_DIR', str(members_instance))
    os.environ.setdefault('ANALYTICS_UPLOAD_ROOT', str(analytics_uploads))

    from app import create_app

    app = create_app()
    app.config.update(TESTING=True)
    yield app


@pytest.fixture()
def client(app):
    return app.test_client()
