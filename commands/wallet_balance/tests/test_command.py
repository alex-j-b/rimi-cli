
"""Generated command-contract test."""

from __future__ import annotations

from pathlib import Path

from www_rimi_ee.testing import run_command_contract


def test_command_contract() -> None:
    run_command_contract(Path(__file__).resolve().parents[1])
