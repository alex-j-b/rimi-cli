from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from www_rimi_ee.runtime import build_app

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]


def test_root_help_lists_descendant_commands() -> None:
    result = CliRunner().invoke(build_app(WORKSPACE_ROOT), ['--help'])

    assert result.exit_code == 0
    assert 'products list' in result.output
    assert 'cart show' in result.output
    assert 'checkout time-slots' in result.output
    assert 'auth store-headers' in result.output


def test_nested_help_lists_descendant_commands_relative_to_group() -> None:
    result = CliRunner().invoke(build_app(WORKSPACE_ROOT), ['products', '--help'])

    assert result.exit_code == 0
    assert 'categories' in result.output
    assert 'get' in result.output
    assert 'list' in result.output
    assert 'cart show' not in result.output
    assert 'products list' not in result.output


def test_command_help_hides_replay_flag() -> None:
    result = CliRunner().invoke(build_app(WORKSPACE_ROOT), ['products', 'categories', '--help'])

    assert result.exit_code == 0
    assert '--replay' not in result.output
