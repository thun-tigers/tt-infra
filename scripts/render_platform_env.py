#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import sys
from datetime import datetime, timezone
from pathlib import Path


def _ensure_repo_root() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))


_ensure_repo_root()

from platform_config import (  # noqa: E402
    OPERATOR_KEYS,
    PROFILE_NAMES,
    flatten_sections,
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
    render_env_parser.add_argument('--include-image-tags', action='store_true', help='Include TIGERS_VERSION (legacy option).')
    render_env_parser.add_argument('--output', type=Path, help='Write to file instead of stdout.')

    render_release_parser = subparsers.add_parser('render-release-manifest', help='Render a release manifest file.')
    render_release_parser.add_argument('--version', required=True, help='Release version, for example 0.1.8.')
    render_release_parser.add_argument('--output', type=Path, help='Write to file instead of stdout.')

    validate_parser = subparsers.add_parser('validate', help='Validate a rendered profile configuration.')
    validate_parser.add_argument('--profile', choices=('local', 'beta', 'production'), required=True)
    validate_parser.add_argument('--version', help='Release version used for image tags, for example 0.1.8.')
    validate_parser.add_argument('--include-image-tags', action='store_true', help='Validate with TIGERS_VERSION (legacy option).')

    generate_parser = subparsers.add_parser(
        'generate',
        help='Generate the internal instance/runtime.env with secrets and derived values.',
    )
    generate_parser.add_argument(
        '--profile', choices=('local', 'beta', 'production'), default='local',
        help='Profile to generate (default: local).',
    )
    generate_parser.add_argument(
        '--version', help='Release version used for image tags, for example 0.1.8.',
    )
    generate_parser.add_argument(
        '--output', type=Path, default=None,
        help='Output file (default: <repo>/instance/runtime.env).',
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
        output_path = args.output or (repo_root / 'instance' / 'runtime.env')
        existing: dict[str, str] = {}
        if output_path.exists():
            for line in output_path.read_text(encoding='utf-8').splitlines():
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    existing[key] = value
        legacy_secrets = repo_root / 'instance' / 'secrets.local.json'
        if not existing and legacy_secrets.exists():
            legacy = json.loads(legacy_secrets.read_text(encoding='utf-8'))
            profile_values = legacy.get(args.profile, {}) if isinstance(legacy, dict) else {}
            if isinstance(profile_values, dict):
                existing.update({str(key): str(value) for key, value in profile_values.items() if value})

        overrides = {key: os.environ[key] for key in OPERATOR_KEYS if os.environ.get(key)}
        secret_keys = (
            'INFRA_SECRET_KEY', 'AUTH_SECRET_KEY', 'MEMBERS_SECRET_KEY',
            'AGENDA_SECRET_KEY', 'ANALYTICS_SECRET_KEY', 'ATTENDANCE_SECRET_KEY',
            'SSO_SHARED_SECRET', 'INTERNAL_API_SECRET', 'DEFAULT_ADMIN_PASSWORD',
            'POSTGRES_INFRA_PASSWORD', 'POSTGRES_AUTH_PASSWORD',
            'POSTGRES_MEMBERS_PASSWORD', 'POSTGRES_AGENDA_PASSWORD',
            'POSTGRES_ANALYTICS_PASSWORD', 'POSTGRES_ATTENDANCE_PASSWORD',
        )
        for key in secret_keys:
            overrides[key] = os.environ.get(key) or existing.get(key) or secrets.token_hex(32)

        suffix = '_beta' if args.profile == 'beta' else ''
        for service in ('infra', 'auth', 'members', 'agenda', 'analytics', 'attendance'):
            upper = service.upper()
            password = overrides[f'POSTGRES_{upper}_PASSWORD']
            overrides[f'{upper}_DATABASE_URL'] = (
                f'postgresql+psycopg://tt_{service}:{password}@tt-postgres:5432/tt_{service}{suffix}'
            )

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
            f'# Source:    profile defaults + environment overrides\n'
            f'# DO NOT EDIT MANUALLY — regenerate via ./scripts/generate-env.sh\n'
            f'\n'
        )
        sections = profile_sections(args.profile, version=render_version, overrides=overrides)
        values = flatten_sections(sections)
        compose_text = (repo_root / 'compose.yml').read_text(encoding='utf-8')
        compose_keys = set(re.findall(r'\$\{([A-Z][A-Z0-9_]*)', compose_text))
        minimal_keys = {'DEPLOYMENT_NAME', 'PUBLIC_BASE_URL', 'TIGERS_VERSION'}
        runtime_keys = sorted(compose_keys - minimal_keys)
        content = header + ''.join(f'{key}={values.get(key, overrides.get(key, ""))}\n' for key in runtime_keys)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content, encoding='utf-8')
        output_path.chmod(0o600)
        print(f'OK: {output_path} written (profile: {args.profile})')

        errors = profile_validation_errors(args.profile, overrides=overrides)
        if errors:
            for error in errors:
                print(f'WARN: {error}', file=sys.stderr)
            if args.profile != 'local':
                print(
                    f'FAIL: required values missing for profile "{args.profile}" — '
                    f'provide the missing value as an environment override and re-run.',
                    file=sys.stderr,
                )
                return 1
        return 0

    parser.error(f'unsupported command: {args.command}')
    return 2


if __name__ == '__main__':
    raise SystemExit(main())
