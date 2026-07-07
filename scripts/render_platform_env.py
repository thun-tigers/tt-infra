#!/usr/bin/env python3

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _ensure_repo_root() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))


_ensure_repo_root()

from platform_config import (  # noqa: E402
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

    parser.error(f'unsupported command: {args.command}')
    return 2


if __name__ == '__main__':
    raise SystemExit(main())
