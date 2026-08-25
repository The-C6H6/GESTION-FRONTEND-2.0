import asyncio
import json

import httpx
import pytest

from esiqie_dictamenes.core.errors import (
    ApiConnectionError,
    ApiTimeoutError,
    AuthenticationError,
    AuthorizationError,
    NotFoundError,
    ServiceUnavailableError,
    UnexpectedResponseError,
    ValidationError,
)
from esiqie_dictamenes.core.settings import ApiSettings
from esiqie_dictamenes.infrastructure.http.api_client import ApiClient
from esiqie_dictamenes.infrastructure.http.token_store import AuthTokenStore


def _client(handler, tokens=None):
    return ApiClient(
        ApiSettings("http://api.test", "/api/auth/login"),
        tokens or AuthTokenStore(),
        transport=httpx.MockTransport(handler),
    )


def test_api_client_sends_json_and_bearer_token():
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "http://api.test/resource"
        assert request.headers["Authorization"] == "Bearer access-secret"
        assert request.headers["Accept"] == "application/json"
        assert request.headers["Content-Type"] == "application/json"
        assert json.loads(request.content) == {"value": 1}
        return httpx.Response(200, json={"ok": True})

    tokens = AuthTokenStore()
    tokens.replace("access-secret", "refresh-secret")

    result = asyncio.run(
        _client(handler, tokens).request_json(
            "POST", "/resource", json={"value": 1}
        )
    )

    assert result == {"ok": True}


def test_api_client_omits_authorization_without_a_token():
    def handler(request: httpx.Request) -> httpx.Response:
        assert "Authorization" not in request.headers
        return httpx.Response(200, json={"ok": True})

    result = asyncio.run(_client(handler).request_json("GET", "/resource"))

    assert result == {"ok": True}


@pytest.mark.parametrize(
    ("status_code", "error_type"),
    [
        (401, AuthenticationError),
        (403, AuthorizationError),
        (404, NotFoundError),
        (422, ValidationError),
        (500, ServiceUnavailableError),
        (503, ServiceUnavailableError),
    ],
)
def test_api_client_maps_http_statuses(status_code, error_type):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, text="technical details")

    with pytest.raises(error_type):
        asyncio.run(_client(handler).request_json("GET", "/resource"))


def test_api_client_maps_connection_failures():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    with pytest.raises(ApiConnectionError):
        asyncio.run(_client(handler).request_json("GET", "/resource"))


def test_api_client_maps_timeouts_separately():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow response", request=request)

    with pytest.raises(ApiTimeoutError):
        asyncio.run(_client(handler).request_json("GET", "/resource"))


def test_api_client_rejects_non_json_responses():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="not-json")

    with pytest.raises(UnexpectedResponseError):
        asyncio.run(_client(handler).request_json("GET", "/resource"))
