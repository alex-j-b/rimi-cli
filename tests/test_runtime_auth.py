from __future__ import annotations

import json

import pytest

from www_rimi_ee import runtime


def test_load_live_header_overrides_prefers_env_over_keyring(monkeypatch: pytest.MonkeyPatch) -> None:
    env_payload = {
        'headers': {
            'cookie': 'from=env',
            'x-xsrf-token': 'env-token',
        }
    }
    monkeypatch.setenv(runtime.PLAYWRIGHT_HEADERS_JSON_ENV, json.dumps(env_payload, separators=(',', ':')))
    monkeypatch.setattr(runtime.keyring, 'get_password', lambda service, account: pytest.fail('keyring should not be used'))

    assert runtime.load_live_header_overrides() == {
        'cookie': 'from=env',
        'x-xsrf-token': 'env-token',
    }


def test_load_live_header_overrides_uses_keyring(monkeypatch: pytest.MonkeyPatch) -> None:
    keyring_payload = {
        'headers': {
            'cookie': 'from=keyring',
            'x-xsrf-token': 'keyring-token',
            'accept': 'application/json',
        }
    }
    monkeypatch.delenv(runtime.PLAYWRIGHT_HEADERS_JSON_ENV, raising=False)
    monkeypatch.setattr(
        runtime.keyring,
        'get_password',
        lambda service, account: json.dumps(keyring_payload, separators=(',', ':')),
    )

    assert runtime.load_live_header_overrides() == {
        'cookie': 'from=keyring',
        'x-xsrf-token': 'keyring-token',
    }


def test_store_playwright_headers_json_writes_system_keyring(monkeypatch: pytest.MonkeyPatch) -> None:
    stored: dict[str, str] = {}
    payload = {
        'headers': {
            'cookie': 'from=store',
            'x-xsrf-token': 'stored-token',
        }
    }

    def fake_set_password(service: str, account: str, password: str) -> None:
        stored['service'] = service
        stored['account'] = account
        stored['password'] = password

    monkeypatch.setattr(runtime.keyring, 'set_password', fake_set_password)

    header_count = runtime.store_playwright_headers_json(json.dumps(payload, separators=(',', ':')))

    assert header_count == 2
    assert stored == {
        'service': runtime.KEYRING_SERVICE,
        'account': runtime.KEYRING_ACCOUNT,
        'password': json.dumps(payload, separators=(',', ':')),
    }
