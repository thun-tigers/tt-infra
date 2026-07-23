import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from platform_config import ESSENTIAL_KEYS, PROFILE_NAMES, PUBLIC_DERIVED_KEYS, profile_sections


def _all_catalog_keys() -> set[str]:
    keys = set()
    for profile in PROFILE_NAMES:
        for section in profile_sections(profile):
            for item in section.entries:
                keys.add(item.key)
    return keys


def test_essential_keys_are_real_catalog_keys():
    unknown = ESSENTIAL_KEYS - _all_catalog_keys()
    assert unknown == set()


def test_essential_keys_do_not_overlap_derived_keys():
    assert ESSENTIAL_KEYS & PUBLIC_DERIVED_KEYS == set()
