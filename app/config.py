import os
from pathlib import Path


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'tt-infra-dev-secret')
    SQLALCHEMY_DATABASE_URI = (
        os.environ.get('SQLALCHEMY_DATABASE_URI')
        or os.environ.get('DATABASE_URL')
        or 'postgresql+psycopg://tt_infra:tt_infra_password@tt-postgres-infra:5432/tt_infra'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    INTERNAL_API_SECRET = os.environ.get('INTERNAL_API_SECRET', 'tt-internal-dev-secret-change-me')
    AUTO_CREATE_DB = os.environ.get('AUTO_CREATE_DB', 'true').lower() == 'true'
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO').upper()
    AUTH_BASE_URL = os.environ.get('AUTH_BASE_URL', 'http://localhost:8085')
    TT_AUTH_INTERNAL_URL = os.environ.get('TT_AUTH_INTERNAL_URL', 'http://tt-auth:5000')
    TT_AGENDA_INTERNAL_URL = os.environ.get('TT_AGENDA_INTERNAL_URL', 'http://tt-agenda:5000')
    SSO_SHARED_SECRET = os.environ.get('SSO_SHARED_SECRET') or SECRET_KEY
    AUTH_DATABASE_URL = os.environ.get('AUTH_DATABASE_URL', 'postgresql+psycopg://tt_auth:tt_auth_password@tt-postgres-auth:5432/tt_auth')
    AGENDA_DATABASE_URL = os.environ.get('AGENDA_DATABASE_URL', 'postgresql+psycopg://tt_agenda:tt_agenda_password@tt-postgres-agenda:5432/tt_agenda')
    ATTENDANCE_DATABASE_URL = os.environ.get('ATTENDANCE_DATABASE_URL', 'postgresql+psycopg://tt_attendance:tt_attendance_password@tt-postgres-attendance:5432/tt_attendance')
    ANALYTICS_DATABASE_URL = os.environ.get('ANALYTICS_DATABASE_URL', 'postgresql+psycopg://tt_analytics:tt_analytics_password@tt-postgres-analytics:5432/tt_analytics')
    MEMBERS_DATABASE_URL = os.environ.get('MEMBERS_DATABASE_URL', 'postgresql+psycopg://tt_members:tt_members_password@tt-postgres-members:5432/tt_members')
    MEMBERS_INSTANCE_DIR = os.environ.get('MEMBERS_INSTANCE_DIR', str(Path('/backup-sources') / 'tt-members-instance'))
    ANALYTICS_UPLOAD_ROOT = os.environ.get('ANALYTICS_UPLOAD_ROOT', str(Path('/backup-sources') / 'tt-analytics-uploads'))
