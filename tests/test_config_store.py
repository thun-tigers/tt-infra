import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine

project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from config_store import (
    has_saved_config,
    load_profile_overrides_from_db,
    load_profile_store_from_db,
    save_profile_store_to_db,
)


@pytest.fixture()
def engine():
    return create_engine('sqlite:///:memory:')


def test_load_from_empty_db_without_fallback_writes_nothing(engine):
    load_profile_store_from_db(engine, fallback_path=None)

    assert has_saved_config(engine) is False
    overrides = load_profile_overrides_from_db(engine)
    assert overrides == {'local': {}, 'beta': {}, 'production': {}}


def test_has_saved_config_becomes_true_only_after_a_real_save(engine):
    assert has_saved_config(engine) is False

    save_profile_store_to_db(engine, {'local': {'DEPLOYMENT_NAME': 'tigers-local'}, 'beta': {}, 'production': {}})

    # save_profile_store_to_db rendert je Profil vollstaendige Snapshots (das
    # ist bestehendes, akzeptiertes Verhalten des regulaeren Speicherns auf
    # /infra/config und gilt fuer alle Profile im uebergebenen store, nicht
    # nur fuer explizit ueberschriebene Felder).
    assert has_saved_config(engine) is True
    overrides = load_profile_overrides_from_db(engine)
    assert overrides['local']['DEPLOYMENT_NAME'] == 'tigers-local'


def test_repeated_reads_of_empty_db_stay_empty(engine):
    load_profile_store_from_db(engine, fallback_path=None)
    load_profile_store_from_db(engine, fallback_path=None)
    load_profile_store_from_db(engine, fallback_path=None)

    assert has_saved_config(engine) is False
