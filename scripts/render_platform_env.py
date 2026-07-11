#!/usr/bin/env python3

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path


def _ensure_repo_root() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))


_ensure_repo_root()

try:  # noqa: E402
    from config_store import load_profile_store_from_db
except ModuleNotFoundError:  # pragma: no cover - fallback for minimal VPS bootstrap
    load_profile_store_from_db = None
from platform_config import (  # noqa: E402
    PROFILE_NAMES,
    load_profile_store as load_profile_store_file,
    profile_sections,
    profile_validation_errors,
    release_manifest_sections,
    render_env,
    render_sections,
    validate_profile,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Render or validate tt-infra platform config.')
    subparsers = parser.add_subparsers(dest='command', required=True)

    render_env_parser = subparsers.add_parser('render-env', help='Render a profile-specific .env file.')
    render_env_parser.add_argument('--profile', choices=('local', 'beta', 'production'), required=True)
    render_env_parser.add_argument('--version', help='Release version used for image tags, for example 0.1.8.')
    render_env_parser.add_argument('--include-image-tags', action='store_true', help='Include TT_*_IMAGE_TAG entries.')
    render_env_parser.add_argument('--output', type=Path, help='Write to file instead of stdout.')

    render_release_parser = subparsers.add_parser('render-release-manifest', help='Render a release manifest file.')
    render_release_parser.add_argument('--version', required=True, help='Release version, for example 0.1.8.')
    render_release_parser.add_argument('--output', type=Path, help='Write to file instead of stdout.')

    validate_parser = subparsers.add_parser('validate', help='Validate a rendered profile configuration.')
    validate_parser.add_argument('--profile', choices=('local', 'beta', 'production'), required=True)
    validate_parser.add_argument('--version', help='Release version used for image tags, for example 0.1.8.')
    validate_parser.add_argument('--include-image-tags', action='store_true', help='Validate with TT_*_IMAGE_TAG entries.')

    generate_parser = subparsers.add_parser(
        'generate',
        help='Generate instance/generated.env from store + profile defaults (bootstrap without running Config-UI).',
    )
    generate_parser.add_argument(
        '--profile', choices=('local', 'beta', 'production'), default='local',
        help='Profile to generate (default: local).',
    )
    generate_parser.add_argument(
        '--version', help='Release version used for image tags, for example 0.1.8.',
    )
    generate_parser.add_argument(
        '--store', type=Path, default=None,
        help='Path to platform-config.json (default: <repo>/instance/platform-config.json).',
    )
    generate_parser.add_argument(
        '--db-url', default=None,
        help='Read the config store from this SQLAlchemy database URL.',
    )
    generate_parser.add_argument(
        '--output', type=Path, default=None,
        help='Output file (default: <repo>/instance/generated.env).',
    )

    return parser


def _write_output(text: str, output: Path | None) -> None:
    if output is None:
        sys.stdout.write(text)
        return
    output.write_text(text, encoding='utf-8')
    print(f'Wrote {output}')


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == 'render-env':
        rendered = render_env(args.profile, version=args.version, include_image_tags=args.include_image_tags)
        _write_output(rendered, args.output)
        return 0

    if args.command == 'render-release-manifest':
        rendered = render_sections(release_manifest_sections(args.version))
        _write_output(rendered, args.output)
        return 0

    if args.command == 'validate':
        errors = validate_profile(args.profile, version=args.version, include_image_tags=args.include_image_tags)
        if errors:
            for error in errors:
                print(f'FAIL: {error}', file=sys.stderr)
            return 1
        print(f'OK: {args.profile} configuration is valid')
        return 0

    if args.command == 'generate':
        repo_root = Path(__file__).resolve().parents[1]
        store_path = args.store or (repo_root / 'instance' / 'platform-config.json')
        output_path = args.output or (repo_root / 'instance' / 'generated.env')
        if args.db_url:
            if load_profile_store_from_db is None:
                print('FAIL: SQLAlchemy ist fuer --db-url nicht verfuegbar.', file=sys.stderr)
                return 1
            from sqlalchemy import create_engine

            engine = create_engine(args.db_url)
            store = load_profile_store_from_db(engine, fallback_path=store_path)
            engine.dispose()
        else:
            store = load_profile_store_file(store_path, seed_defaults=True)
            secret_path = store_path.with_name('secrets.local.json')
            if secret_path.exists():
                secret_store = load_profile_store_file(secret_path, seed_defaults=False)
                for profile in PROFILE_NAMES:
                    store[profile].update(secret_store.get(profile, {}))
        overrides = store.get(args.profile, {})

        timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
        render_version = args.version
        if render_version is None and args.profile in {'beta', 'production'}:
            version_file = repo_root / 'VERSION'
            if version_file.exists():
                render_version = version_file.read_text(encoding='utf-8').strip()
        header = (
            f'# Generated by tt-infra\n'
            f'# Profile:   {args.profile}\n'
            f'# Generated: {timestamp}\n'
            f'# Source:    tt-infra config DB or export files\n'
            f'# DO NOT EDIT MANUALLY — regenerate via ./scripts/generate-env.sh or Config-UI /config\n'
            f'\n'
        )
        content = header + render_sections(profile_sections(args.profile, version=render_version, overrides=overrides))

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content, encoding='utf-8')
        print(f'OK: {output_path} written (profile: {args.profile})')

        errors = profile_validation_errors(args.profile, overrides=overrides)
        if errors:
            for error in errors:
                print(f'WARN: {error}', file=sys.stderr)
            if args.profile != 'local':
                print(
                    f'FAIL: required values missing for profile "{args.profile}" — '
                    f'open Config-UI at /config, fill in secrets, save, then re-run.',
                    file=sys.stderr,
                )
                return 1
        return 0

    parser.error(f'unsupported command: {args.command}')
    return 2


if __name__ == '__main__':
    raise SystemExit(main())
