#!/usr/bin/env python3

"""Render a single Arcane env file from a base env and a release manifest.

The base file keeps secrets and runtime settings. The release manifest only
overrides the image tags, which makes it safe to pin a deployable stack to a
specific platform release while still using one env file in Arcane.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, List, Tuple


def parse_env_lines(path: Path) -> Tuple[List[str], Dict[str, str]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    values: Dict[str, str] = {}
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value
    return lines, values


def render_merged_env(base_path: Path, overlay_path: Path) -> str:
    base_lines, base_values = parse_env_lines(base_path)
    _, overlay_values = parse_env_lines(overlay_path)

    merged = dict(base_values)
    merged.update(overlay_values)

    rendered: List[str] = []
    seen: set[str] = set()

    for line in base_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            rendered.append(line)
            continue
        key, _ = line.split("=", 1)
        key = key.strip()
        if key in merged:
            rendered.append(f"{key}={merged[key]}")
            seen.add(key)
        else:
            rendered.append(line)

    for key, value in overlay_values.items():
        if key not in seen and key not in base_values:
            rendered.append(f"{key}={value}")

    return "\n".join(rendered) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Merge a base env file with a release manifest for Arcane."
    )
    parser.add_argument("--base", required=True, type=Path, help="Base env file")
    parser.add_argument(
        "--overlay", required=True, type=Path, help="Release manifest env file"
    )
    parser.add_argument("--output", required=True, type=Path, help="Output env file")
    args = parser.parse_args()

    rendered = render_merged_env(args.base, args.overlay)
    args.output.write_text(rendered, encoding="utf-8")
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
