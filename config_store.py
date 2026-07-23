from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from sqlalchemy import Column, DateTime, MetaData, String, Table, Text, delete, func, select
from sqlalchemy.engine import Engine

from platform_config import (
    PROFILE_NAMES,
    PUBLIC_DERIVED_KEYS,
    infer_field_kind,
    is_secret_key,
    load_profile_store as load_profile_store_file,
    profile_sections,
    profile_values,
    save_profile_store as save_profile_store_file,
)


metadata = MetaData()

platform_settings = Table(
    'platform_settings',
    metadata,
    Column('profile', String(32), primary_key=True),
    Column('key', String(128), primary_key=True),
    Column('value', Text, nullable=False, default=''),
    Column('value_type', String(32), nullable=False, default='text'),
    Column('category', String(128), nullable=False, default=''),
    Column('description', Text, nullable=False, default=''),
    Column('created_at', DateTime(timezone=True), nullable=False),
    Column('updated_at', DateTime(timezone=True), nullable=False),
)

platform_secrets = Table(
    'platform_secrets',
    metadata,
    Column('profile', String(32), primary_key=True),
    Column('key', String(128), primary_key=True),
    Column('value', Text, nullable=False, default=''),
    Column('value_type', String(32), nullable=False, default='password'),
    Column('category', String(128), nullable=False, default=''),
    Column('description', Text, nullable=False, default=''),
    Column('created_at', DateTime(timezone=True), nullable=False),
    Column('updated_at', DateTime(timezone=True), nullable=False),
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def ensure_schema(engine: Engine) -> None:
    metadata.create_all(engine)


def _empty_store() -> dict[str, dict[str, str]]:
    return {profile: {} for profile in PROFILE_NAMES}


def _public_only_store(store: dict[str, dict[str, str]]) -> dict[str, dict[str, str]]:
    result = _empty_store()
    for profile, values in store.items():
        result[profile] = {
            key: value
            for key, value in values.items()
            if not is_secret_key(key) and key not in PUBLIC_DERIVED_KEYS
        }
    return result


def _secret_only_store(store: dict[str, dict[str, str]]) -> dict[str, dict[str, str]]:
    result = _empty_store()
    for profile, values in store.items():
        result[profile] = {
            key: value
            for key, value in values.items()
            if is_secret_key(key) and key not in PUBLIC_DERIVED_KEYS
        }
    return result


def _section_metadata(profile: str) -> dict[str, tuple[str, str]]:
    metadata_map: dict[str, tuple[str, str]] = {}
    for section in profile_sections(profile):
        for item in section.entries:
            if item.key in PUBLIC_DERIVED_KEYS:
                continue
            metadata_map[item.key] = (section.title, infer_field_kind(item.key))
    return metadata_map


def _rows_from_store(profile: str, values: dict[str, str]) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    metadata_map = _section_metadata(profile)
    rendered = profile_values(profile, overrides=values)
    now = _now()
    settings_rows: list[dict[str, object]] = []
    secret_rows: list[dict[str, object]] = []
    for key, value in rendered.items():
        if key in PUBLIC_DERIVED_KEYS:
            continue
        category, value_type = metadata_map.get(key, ('', infer_field_kind(key)))
        row = {
            'profile': profile,
            'key': key,
            'value': '' if value is None else str(value),
            'value_type': value_type,
            'category': category,
            'description': '',
            'created_at': now,
            'updated_at': now,
        }
        if is_secret_key(key):
            secret_rows.append(row | {'value_type': 'password'})
        else:
            settings_rows.append(row | {'value_type': value_type})
    return settings_rows, secret_rows


def save_profile_store_to_db(engine: Engine, store: dict[str, dict[str, str]]) -> None:
    ensure_schema(engine)
    now = _now()
    with engine.begin() as conn:
        for profile in PROFILE_NAMES:
            conn.execute(delete(platform_settings).where(platform_settings.c.profile == profile))
            conn.execute(delete(platform_secrets).where(platform_secrets.c.profile == profile))
            settings_rows, secret_rows = _rows_from_store(profile, store.get(profile, {}))
            if settings_rows:
                conn.execute(platform_settings.insert(), settings_rows)
            if secret_rows:
                conn.execute(platform_secrets.insert(), secret_rows)


def _read_profile_rows(engine: Engine, table: Table) -> dict[str, dict[str, str]]:
    values = _empty_store()
    with engine.begin() as conn:
        for row in conn.execute(select(table.c.profile, table.c.key, table.c.value)):
            values[row.profile][row.key] = '' if row.value is None else str(row.value)
    return values


def has_saved_config(engine: Engine) -> bool:
    """True, sobald irgendwer irgendein Profil je gespeichert hat.

    Dient dem Setup-Assistenten als "ist das ein Erstdeploy?"-Signal. Erst
    nach dem ersten echten Save (egal welches Profil/Feld) liefert dies True.
    """
    ensure_schema(engine)
    with engine.begin() as conn:
        settings_count = conn.execute(select(func.count()).select_from(platform_settings)).scalar_one()
        secrets_count = conn.execute(select(func.count()).select_from(platform_secrets)).scalar_one()
    return bool(settings_count or secrets_count)


def load_profile_overrides_from_db(engine: Engine) -> dict[str, dict[str, str]]:
    """Nur die tatsaechlich gespeicherten (sparsen) Overrides, ohne Defaults.

    Fuer Stellen, die gezielt NUR ein paar Felder speichern wollen (z.B. der
    Setup-Assistent) - im Gegensatz zu load_profile_store_from_db(), das fuer
    die Anzeige immer die volle, mit Defaults gemergte Sicht liefert.
    """
    ensure_schema(engine)
    settings_store = _read_profile_rows(engine, platform_settings)
    secret_store = _read_profile_rows(engine, platform_secrets)
    merged = _empty_store()
    for profile in PROFILE_NAMES:
        raw_values = dict(settings_store.get(profile, {}))
        raw_values.update(secret_store.get(profile, {}))
        merged[profile] = raw_values
    return merged


def load_profile_store_from_db(
    engine: Engine,
    *,
    seed_defaults: bool = True,
    fallback_path: Path | None = None,
) -> dict[str, dict[str, str]]:
    ensure_schema(engine)

    with engine.begin() as conn:
        settings_count = conn.execute(select(func.count()).select_from(platform_settings)).scalar_one()
        secrets_count = conn.execute(select(func.count()).select_from(platform_secrets)).scalar_one()
        has_rows = bool(settings_count or secrets_count)

    if not has_rows and fallback_path and fallback_path.exists():
        # Einmalige Migration aus der alten datei-basierten Speicherung. Ein
        # leerer Start ohne Fallback-Datei schreibt bewusst NICHTS in die DB -
        # has_rows bleibt sonst nach jedem Read faelschlich True, weil hier
        # samtliche Profil-Defaults dauerhaft als "explizite" Werte eingefroren
        # wuerden. Spaetere Verbesserungen an einem Default in platform_config.py
        # kaemen dann nie mehr durch, und has_rows waere fuer den Setup-
        # Assistenten kein ehrliches "wurde hier schon je etwas gespeichert"-Signal.
        store = load_profile_store_file(fallback_path, seed_defaults=seed_defaults)
        secret_path = fallback_path.with_name('secrets.local.json')
        if secret_path.exists():
            secret_store = load_profile_store_file(secret_path, seed_defaults=False)
            for profile in PROFILE_NAMES:
                store[profile].update(secret_store.get(profile, {}))
        save_profile_store_to_db(engine, store)

    settings_store = _read_profile_rows(engine, platform_settings)
    secret_store = _read_profile_rows(engine, platform_secrets)

    merged = _empty_store()
    for profile in PROFILE_NAMES:
        raw_values = dict(settings_store.get(profile, {}))
        raw_values.update(secret_store.get(profile, {}))
        merged[profile] = profile_values(profile, overrides=raw_values)
    if seed_defaults:
        for profile in PROFILE_NAMES:
            defaults = profile_values(profile)
            for key, value in defaults.items():
                merged[profile].setdefault(key, value)
    return merged


def export_profile_store_to_path(path: Path, store: dict[str, dict[str, str]]) -> None:
    save_profile_store_file(path, _public_only_store(store))


def export_secret_store_to_path(path: Path, store: dict[str, dict[str, str]]) -> None:
    save_profile_store_file(path, _secret_only_store(store))


def import_profile_store_from_path(path: Path) -> dict[str, dict[str, str]]:
    return load_profile_store_file(path, seed_defaults=True)
