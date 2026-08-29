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
from esiqie_dictamenes.core.session import AuthSessionStore
from esiqie_dictamenes.infrastructure.http.api_client import ApiClient
from tests.helpers import api_settings, authenticated_user


def _client(handler, store=None):
    return ApiClient(
        api_settings(),
        store or AuthSessionStore(),
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

    store = AuthSessionStore()
    store.begin("access-secret", "refresh-secret")

    result = asyncio.run(
        _client(handler, store).request_json(
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


def test_api_client_can_omit_authorization_with_an_existing_session():
    def handler(request: httpx.Request) -> httpx.Response:
        assert "Authorization" not in request.headers
        return httpx.Response(200, json={"ok": True})

    store = AuthSessionStore()
    store.begin("access-secret", "refresh-secret")

    result = asyncio.run(
        _client(handler, store).request_json(
            "POST",
            "/api/auth/login",
            authenticated=False,
        )
    )

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


def test_api_client_clears_the_session_when_it_expires():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"detail": "expired token"})

    store = AuthSessionStore()
    store.begin("expired-access", "expired-refresh")

    with pytest.raises(SessionExpiredError):
        asyncio.run(_client(handler, store).request_json("GET", "/resource"))

    assert store.current is None


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


def test_api_client_refreshes_and_replays_the_exact_request_once():
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/api/auth/refresh":
            return httpx.Response(
                200,
                json={
                    "access_token": "new-access",
                    "refresh_token": "new-refresh",
                },
            )
        if request.headers["Authorization"] == "Bearer old-access":
            return httpx.Response(401)
        return httpx.Response(200, json={"ok": True})

    store = AuthSessionStore()
    store.begin("old-access", "old-refresh")

    result = asyncio.run(
        _client(handler, store).request_json(
            "PUT",
            "/resource",
            json={"value": 1},
            params={"page": 2},
            expected_status=200,
        )
    )

    assert result == {"ok": True}
    assert [(request.method, request.url.path) for request in requests] == [
        ("PUT", "/resource"),
        ("POST", "/api/auth/refresh"),
        ("PUT", "/resource"),
    ]
    assert json.loads(requests[1].content) == {
        "refresh_token": "old-refresh"
    }
    assert "Authorization" not in requests[1].headers
    assert requests[2].headers["Authorization"] == "Bearer new-access"
    assert json.loads(requests[2].content) == {"value": 1}
    assert dict(requests[2].url.params) == {"page": "2"}
    assert store.current is not None
    assert store.current.access_token == "new-access"
    assert store.current.refresh_token == "new-refresh"


def test_api_client_does_not_refresh_a_successful_request():
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"ok": True})

    store = AuthSessionStore()
    store.begin("access-token", "refresh-token")

    result = asyncio.run(
        _client(handler, store).request_json("GET", "/resource")
    )

    assert result == {"ok": True}
    assert [(request.method, request.url.path) for request in requests] == [
        ("GET", "/resource")
    ]


@pytest.mark.parametrize("refresh_status", [401, 403])
def test_api_client_clears_the_session_when_refresh_is_rejected(
    refresh_status,
):
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/api/auth/refresh":
            return httpx.Response(refresh_status)
        return httpx.Response(401)

    store = AuthSessionStore()
    store.begin("old-access", "old-refresh")

    with pytest.raises(SessionExpiredError):
        asyncio.run(_client(handler, store).request_json("GET", "/resource"))

    assert [(request.method, request.url.path) for request in requests] == [
        ("GET", "/resource"),
        ("POST", "/api/auth/refresh"),
    ]
    assert store.current is None


@pytest.mark.parametrize("refresh_token", [None, ""])
def test_api_client_expires_a_session_without_refresh_state(refresh_token):
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(401)

    store = AuthSessionStore()
    if refresh_token is not None:
        store.begin("old-access", refresh_token)

    with pytest.raises(SessionExpiredError):
        asyncio.run(_client(handler, store).request_json("GET", "/resource"))

    assert [(request.method, request.url.path) for request in requests] == [
        ("GET", "/resource")
    ]
    assert store.current is None


@pytest.mark.parametrize("malformed_response", ["invalid-json", "token-pair"])
def test_api_client_clears_the_session_for_a_malformed_refresh_payload(
    malformed_response,
):
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path != "/api/auth/refresh":
            return httpx.Response(401)
        if malformed_response == "invalid-json":
            return httpx.Response(200, text="not-json")
        return httpx.Response(200, json={"access_token": "new-access"})

    store = AuthSessionStore()
    store.begin("old-access", "old-refresh")

    with pytest.raises(UnexpectedResponseError):
        asyncio.run(_client(handler, store).request_json("GET", "/resource"))

    assert [request.url.path for request in requests] == [
        "/resource",
        "/api/auth/refresh",
    ]
    assert store.current is None


def test_api_client_clears_the_session_when_the_single_replay_is_unauthorized():
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/api/auth/refresh":
            return httpx.Response(
                200,
                json={
                    "access_token": "new-access",
                    "refresh_token": "new-refresh",
                },
            )
        return httpx.Response(401)

    store = AuthSessionStore()
    store.begin("old-access", "old-refresh")

    with pytest.raises(SessionExpiredError):
        asyncio.run(_client(handler, store).request_json("GET", "/resource"))

    assert [(request.method, request.url.path) for request in requests] == [
        ("GET", "/resource"),
        ("POST", "/api/auth/refresh"),
        ("GET", "/resource"),
    ]
    assert store.current is None


@pytest.mark.parametrize(
    ("refresh_result", "expected_error"),
    [
        ("timeout", ApiTimeoutError),
        ("connection", ApiConnectionError),
        ("service-unavailable", ServiceUnavailableError),
    ],
)
def test_api_client_preserves_an_established_session_for_transient_refresh_errors(
    refresh_result,
    expected_error,
):
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path != "/api/auth/refresh":
            return httpx.Response(401)
        if refresh_result == "timeout":
            raise httpx.ReadTimeout("slow refresh", request=request)
        if refresh_result == "connection":
            raise httpx.ConnectError("failed refresh", request=request)
        return httpx.Response(503)

    store = AuthSessionStore()
    original = store.begin("old-access", "old-refresh")
    store.authenticate(authenticated_user())

    with pytest.raises(expected_error):
        asyncio.run(_client(handler, store).request_json("GET", "/resource"))

    assert [request.url.path for request in requests] == [
        "/resource",
        "/api/auth/refresh",
    ]
    assert store.current is original
    assert store.current.access_token == "old-access"
    assert store.current.refresh_token == "old-refresh"
    assert store.current.current_user == authenticated_user()


def test_api_client_can_retry_refresh_after_an_independent_transient_failure():
    async def scenario():
        refresh_calls = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal refresh_calls
            if request.url.path == "/api/auth/refresh":
                refresh_calls += 1
                if refresh_calls == 1:
                    return httpx.Response(503)
                return httpx.Response(
                    200,
                    json={
                        "access_token": "new-access",
                        "refresh_token": "new-refresh",
                    },
                )
            if request.headers["Authorization"] == "Bearer old-access":
                return httpx.Response(401)
            return httpx.Response(200, json={"ok": True})

        store = AuthSessionStore()
        original = store.begin("old-access", "old-refresh")
        store.authenticate(authenticated_user())
        client = ApiClient(
            api_settings(),
            store,
            transport=httpx.MockTransport(handler),
        )

        with pytest.raises(ServiceUnavailableError):
            await client.request_json("GET", "/resource")

        assert store.current is original
        assert store.current.access_token == "old-access"
        assert store.current.refresh_token == "old-refresh"

        result = await client.request_json("GET", "/resource")

        assert result == {"ok": True}
        assert refresh_calls == 2
        assert store.current is original
        assert store.current.access_token == "new-access"
        assert store.current.refresh_token == "new-refresh"

    asyncio.run(scenario())


def test_api_client_preserves_the_session_and_does_not_refresh_a_forbidden_request():
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(403)

    store = AuthSessionStore()
    original = store.begin("old-access", "old-refresh")

    with pytest.raises(AuthorizationError):
        asyncio.run(_client(handler, store).request_json("GET", "/resource"))

    assert [request.url.path for request in requests] == ["/resource"]
    assert store.current is original
    assert store.current.access_token == "old-access"
    assert store.current.refresh_token == "old-refresh"


def test_api_client_recovery_logs_exclude_all_request_and_token_data(caplog):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/auth/refresh":
            return httpx.Response(
                200,
                json={
                    "access_token": "new-access-secret",
                    "refresh_token": "new-refresh-secret",
                },
            )
        if request.headers["Authorization"] == "Bearer old-access-secret":
            return httpx.Response(401)
        raise httpx.ReadTimeout("replay timeout", request=request)

    store = AuthSessionStore()
    store.begin("old-access-secret", "old-refresh-secret")

    with caplog.at_level(logging.WARNING), pytest.raises(ApiTimeoutError):
        asyncio.run(
            _client(handler, store).request_json(
                "POST",
                "/private/secret-path",
                json={"secret": "payload-secret"},
                params={"query": "query-secret"},
            )
        )

    assert "API request timed out" in caplog.text
    for sensitive_value in (
        "old-access-secret",
        "old-refresh-secret",
        "new-access-secret",
        "new-refresh-secret",
        "secret-path",
        "payload-secret",
        "query-secret",
    ):
        assert sensitive_value not in caplog.text


def test_api_client_shares_one_refresh_without_cross_wiring_concurrent_requests():
    async def scenario():
        both_old_requests_arrived = asyncio.Event()
        old_token_calls = 0
        new_token_calls = 0
        refresh_calls = 0

        async def handler(request: httpx.Request) -> httpx.Response:
            nonlocal old_token_calls, new_token_calls, refresh_calls
            if request.url.path == "/api/auth/refresh":
                refresh_calls += 1
                return httpx.Response(
                    200,
                    json={
                        "access_token": "new-access",
                        "refresh_token": "new-refresh",
                    },
                )
            if request.headers["Authorization"] == "Bearer old-access":
                old_token_calls += 1
                if old_token_calls == 2:
                    both_old_requests_arrived.set()
                await both_old_requests_arrived.wait()
                return httpx.Response(401)
            assert request.headers["Authorization"] == "Bearer new-access"
            new_token_calls += 1
            return httpx.Response(
                200,
                json={"request": request.url.params["request"]},
            )

        store = AuthSessionStore()
        store.begin("old-access", "old-refresh")
        client = ApiClient(
            api_settings(),
            store,
            transport=httpx.MockTransport(handler),
        )

        results = await asyncio.gather(
            client.request_json("GET", "/resource", params={"request": 1}),
            client.request_json("GET", "/resource", params={"request": 2}),
        )

        assert results == [{"request": "1"}, {"request": "2"}]
        assert refresh_calls == 1
        assert old_token_calls == 2
        assert new_token_calls == 2

    asyncio.run(scenario())
