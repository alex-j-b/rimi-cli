from __future__ import annotations

import json

import httpx
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
    monkeypatch.setattr(
        runtime.keyring, 'get_password', lambda service, account: pytest.fail('keyring should not be used')
    )

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


def test_refresh_stored_session_headers_merges_and_stores_new_cookies(monkeypatch: pytest.MonkeyPatch) -> None:
    stored: dict[str, str] = {}
    payload = {
        'headers': {
            'cookie': 'rimi_storefront_session=old; keep=yes; XSRF-TOKEN=old-xsrf',
            'x-xsrf-token': 'old-xsrf',
        }
    }

    class FakeClient:
        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs
            self.cookies = httpx.Cookies()

        def __enter__(self) -> FakeClient:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def get(
            self,
            url: str,
            *,
            headers: dict[str, str] | None = None,
            params: dict[str, str] | None = None,
        ) -> httpx.Response:
            request = httpx.Request('GET', url, headers=headers, params=params)
            if url == runtime.RIMI_LOGIN_URL:
                self.cookies.set('rimi_storefront_session', 'new-session', domain='www.rimi.ee', path='/')
                self.cookies.set('XSRF-TOKEN', 'new%20xsrf', domain='www.rimi.ee', path='/')
                return httpx.Response(200, request=request, content=b'<html></html>')
            if url == runtime.RIMI_WHOAMI_URL:
                return httpx.Response(200, request=request, json={'userName': 'Test User'})
            raise AssertionError(f'unexpected URL: {url}')

    def fake_set_password(service: str, account: str, password: str) -> None:
        stored['service'] = service
        stored['account'] = account
        stored['password'] = password

    monkeypatch.delenv(runtime.PLAYWRIGHT_HEADERS_JSON_ENV, raising=False)
    monkeypatch.setattr(
        runtime.keyring, 'get_password', lambda service, account: json.dumps(payload, separators=(',', ':'))
    )
    monkeypatch.setattr(runtime.keyring, 'set_password', fake_set_password)
    monkeypatch.setattr(runtime.httpx, 'Client', FakeClient)

    result = runtime.refresh_stored_session_headers()

    refreshed_payload = json.loads(stored['password'])
    assert result == {
        'refreshed': True,
        'signed_in': True,
        'stored_header_count': 2,
        'user_name': 'Test User',
    }
    assert refreshed_payload['headers']['cookie'] == (
        'rimi_storefront_session=new-session; keep=yes; XSRF-TOKEN=new%20xsrf'
    )
    assert refreshed_payload['headers']['x-xsrf-token'] == 'new xsrf'


def test_refresh_stored_session_headers_requires_headers_object(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(runtime.PLAYWRIGHT_HEADERS_JSON_ENV, raising=False)
    monkeypatch.setattr(runtime.keyring, 'get_password', lambda service, account: '{}')

    with pytest.raises(ValueError, match='stored Playwright headers JSON must contain a headers object'):
        runtime.refresh_stored_session_headers()


def test_refresh_stored_session_headers_reports_external_sso_redirect(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        'headers': {
            'cookie': 'rimi_storefront_session=old; XSRF-TOKEN=old-xsrf',
            'x-xsrf-token': 'old-xsrf',
        }
    }

    class FakeClient:
        cookies = httpx.Cookies()

        def __enter__(self) -> FakeClient:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def get(self, url: str, *, headers: dict[str, str] | None = None) -> httpx.Response:
            request = httpx.Request('GET', 'https://sso.example.test/login', headers=headers)
            return httpx.Response(200, request=request)

    monkeypatch.delenv(runtime.PLAYWRIGHT_HEADERS_JSON_ENV, raising=False)
    monkeypatch.setattr(
        runtime.keyring, 'get_password', lambda service, account: json.dumps(payload, separators=(',', ':'))
    )
    monkeypatch.setattr(
        runtime.keyring,
        'set_password',
        lambda service, account, password: pytest.fail('external SSO redirects should not be stored'),
    )
    monkeypatch.setattr(runtime.httpx, 'Client', lambda **kwargs: FakeClient())

    with pytest.raises(ValueError, match='external SSO login page'):
        runtime.refresh_stored_session_headers()
