import asyncio
import json
import logging

import httpx
import pytest

from esiqie_dictamenes.core.errors import (
    ApiConnectionError,
    ApiTimeoutError,
    AuthorizationError,
    BadRequestError,
    NotFoundError,
    SessionExpiredError,
    ServiceUnavailableError,
    UnexpectedResponseError,
    ValidationError,
)
from esiqie_dictamenes.core.settings import ApiSettings
from esiqie_dictamenes.infrastructure.http.api_client import ApiClient
from esiqie_dictamenes.infrastructure.http.token_store import AuthTokenStore


def _client(handler, tokens=None):
    return ApiClient(
        ApiSettings(
            "http://api.test",
            "/api/auth/login",
            "/api/inscritos/{boleta}",
            "/api/reprobados",
            "/api/dictaminaciones",
            "/api/dictaminaciones",
        ),
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


def test_api_client_can_require_the_exact_success_status():
    client = _client(
        lambda request: httpx.Response(201, json={"Clave": "CSE-0001-26"})
    )

    result = asyncio.run(
        client.request_json(
            "POST",
            "/api/dictaminaciones",
            json={"value": 1},
            expected_status=201,
        )
    )

    assert result == {"Clave": "CSE-0001-26"}


def test_api_client_rejects_a_different_success_status_when_exact_is_required():
    client = _client(lambda request: httpx.Response(200, json={"ok": True}))

    with pytest.raises(UnexpectedResponseError):
        asyncio.run(
            client.request_json(
                "POST",
                "/api/dictaminaciones",
                json={"value": 1},
                expected_status=201,
            )
        )


def test_api_client_omits_authorization_without_a_token():
    def handler(request: httpx.Request) -> httpx.Response:
        assert "Authorization" not in request.headers
        return httpx.Response(200, json={"ok": True})

    result = asyncio.run(_client(handler).request_json("GET", "/resource"))

    assert result == {"ok": True}


def test_api_client_sends_query_parameters_without_changing_the_path():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/reprobados"
        assert request.url.params.get("boleta") == "2022630000"
        return httpx.Response(200, json={"items": []})

    result = asyncio.run(
        _client(handler).request_json(
            "GET",
            "/api/reprobados",
            params={"boleta": "2022630000"},
        )
    )

    assert result == {"items": []}


def test_api_client_accepts_integer_query_parameters():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.query == b"anio=2026&skip=100&limit=100"
        return httpx.Response(200, json={"items": []})

    result = asyncio.run(
        _client(handler).request_json(
            "GET",
            "/api/dictaminaciones",
            params={"anio": 2026, "skip": 100, "limit": 100},
        )
    )

    assert result == {"items": []}


def test_api_client_exposes_only_the_safe_400_detail_to_repositories():
    client = _client(
        lambda request: httpx.Response(
            400,
            json={"detail": "No se encontraron dictaminaciones."},
        )
    )

    with pytest.raises(BadRequestError) as captured:
        asyncio.run(client.request_json("GET", "/api/dictaminaciones"))

    assert captured.value.detail == "No se encontraron dictaminaciones."
    assert "dictaminaciones" not in str(captured.value)


@pytest.mark.parametrize(
    ("status_code", "error_type"),
    [
        (401, SessionExpiredError),
        (400, ValidationError),
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


def test_api_client_clears_tokens_when_the_session_expires():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"detail": "expired token"})

    tokens = AuthTokenStore()
    tokens.replace("expired-access", "expired-refresh")

    with pytest.raises(SessionExpiredError):
        asyncio.run(_client(handler, tokens).request_json("GET", "/resource"))

    assert tokens.access_token is None


def test_api_client_maps_timeouts_separately():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow response", request=request)

    with pytest.raises(ApiTimeoutError):
        asyncio.run(_client(handler).request_json("GET", "/resource"))


def test_api_client_does_not_log_sensitive_request_paths(caplog):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow response", request=request)

    with caplog.at_level(logging.WARNING), pytest.raises(ApiTimeoutError):
        asyncio.run(
            _client(handler).request_json(
                "GET", "/api/inscritos/2022630000"
            )
        )

    assert "API request timed out" in caplog.text
    assert "2022630000" not in caplog.text


def test_api_client_rejects_non_json_responses():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="not-json")

    with pytest.raises(UnexpectedResponseError):
        asyncio.run(_client(handler).request_json("GET", "/resource"))
