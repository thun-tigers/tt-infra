import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
scripts_dir = project_root / 'scripts'
if str(scripts_dir) not in sys.path:
    sys.path.insert(0, str(scripts_dir))

import render_platform_env as rpe


def _read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding='utf-8').splitlines():
        if line and not line.startswith('#') and '=' in line:
            key, value = line.split('=', 1)
            values[key] = value
    return values


def test_generate_picks_up_non_secret_value_from_config_ui(tmp_path):
    config_ui_path = tmp_path / 'generated.env'
    config_ui_path.write_text('AGENDA_SSO_EXPECTED_AUDIENCE=custom-aud\n', encoding='utf-8')
    output_path = tmp_path / 'runtime.env'

    exit_code = rpe.main([
        'generate', '--profile', 'local',
        '--output', str(output_path),
        '--config-ui-path', str(config_ui_path),
    ])

    assert exit_code == 0
    values = _read_env(output_path)
    assert values.get('AGENDA_SSO_EXPECTED_AUDIENCE') == 'custom-aud'


def test_generate_never_lets_stale_config_ui_value_override_an_existing_secret(tmp_path):
    output_path = tmp_path / 'runtime.env'
    output_path.write_text('AUTH_SECRET_KEY=already-rotated-secret\n', encoding='utf-8')
    config_ui_path = tmp_path / 'generated.env'
    config_ui_path.write_text('AUTH_SECRET_KEY=stale-value-from-old-save\n', encoding='utf-8')

    exit_code = rpe.main([
        'generate', '--profile', 'local',
        '--output', str(output_path),
        '--config-ui-path', str(config_ui_path),
    ])

    assert exit_code == 0
    values = _read_env(output_path)
    assert values.get('AUTH_SECRET_KEY') == 'already-rotated-secret'


def test_generate_without_config_ui_file_is_unchanged(tmp_path):
    output_path = tmp_path / 'runtime.env'
    config_ui_path = tmp_path / 'generated.env'  # bewusst nicht angelegt (Blank-Server-Fall)

    exit_code = rpe.main([
        'generate', '--profile', 'local',
        '--output', str(output_path),
        '--config-ui-path', str(config_ui_path),
    ])

    assert exit_code == 0
    assert output_path.exists()
    values = _read_env(output_path)
    assert values.get('AGENDA_SSO_EXPECTED_AUDIENCE') == 'tt-agenda'
