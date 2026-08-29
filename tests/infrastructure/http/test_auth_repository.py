import asyncio
import json

import httpx
import pytest

from esiqie_dictamenes.core.errors import (
    ApiConnectionError,
    ApiTimeoutError,
    AuthenticationError,
    AuthorizationError,
    InactiveUserError,
    ServiceUnavailableError,
    SessionExpiredError,
    UnexpectedResponseError,
)
from esiqie_dictamenes.core.session import AuthSessionStore
from esiqie_dictamenes.infrastructure.http.api_client import ApiClient
from esiqie_dictamenes.infrastructure.http.auth_repository import ApiAuthRepository
from tests.helpers import api_settings, authenticated_user


def repository_and_store(handler):
    settings = api_settings()
    store = AuthSessionStore()
    client = ApiClient(
        settings,
        store,
        transport=httpx.MockTransport(handler),
    )
    return (
        ApiAuthRepository(
            client,
            store,
            settings.login_path,
            settings.auth_me_path,
        ),
        store,
    )


@pytest.mark.parametrize("is_admin", [True, False])
def test_api_login_publishes_only_the_identity_returned_by_auth_me(is_admin):
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/api/auth/login":
            assert request.method == "POST"
            assert "Authorization" not in request.headers
            assert json.loads(request.content) == {
                "username": "submitted-name",
                "password": "secreto",
            }
            return httpx.Response(
                200,
                json={
                    "access_token": "access-token",
                    "refresh_token": "refresh-token",
                },
            )
        assert request.method == "GET"
        assert request.url.path == "/api/auth/me"
        assert request.headers["Authorization"] == "Bearer access-token"
        return httpx.Response(
            200,
            json={
                "id": 7,
                "username": "identity-from-api",
                "is_active": True,
                "is_admin": is_admin,
            },
        )

    repository, store = repository_and_store(handler)
    session = asyncio.run(repository.login("submitted-name", "secreto"))

    assert [request.url.path for request in requests] == [
        "/api/auth/login",
        "/api/auth/me",
    ]
    assert session is store.current
    assert session.current_user is not None
    assert session.current_user.username == "identity-from-api"
    assert session.current_user.is_admin is is_admin


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {"username": "user", "is_active": True, "is_admin": False},
        {"id": 7, "is_active": True, "is_admin": False},
        {"id": 7, "username": "user", "is_admin": False},
        {"id": 7, "username": "user", "is_active": True},
        {"id": True, "username": "user", "is_active": True, "is_admin": False},
        {"id": 7, "username": "   ", "is_active": True, "is_admin": False},
        {"id": 7, "username": "user", "is_active": 1, "is_admin": False},
        {"id": 7, "username": "user", "is_active": True, "is_admin": 0},
    ],
)
def test_api_login_rejects_malformed_auth_me_payload_and_clears_pending_session(
    payload,
):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/auth/login":
            return httpx.Response(
                200,
                json={
                    "access_token": "access-token",
                    "refresh_token": "refresh-token",
                },
            )
        return httpx.Response(200, json=payload)

    repository, store = repository_and_store(handler)

    with pytest.raises(UnexpectedResponseError):
        asyncio.run(repository.login("directivo", "secreto"))

    assert store.current is None


def test_api_login_rejects_inactive_identity_and_clears_pending_session():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/auth/login":
            return httpx.Response(
                200,
                json={
                    "access_token": "access-token",
                    "refresh_token": "refresh-token",
                },
            )
        return httpx.Response(
            200,
            json={
                "id": 7,
                "username": "inactive-user",
                "is_active": False,
                "is_admin": False,
            },
        )

    repository, store = repository_and_store(handler)

    with pytest.raises(InactiveUserError) as captured:
        asyncio.run(repository.login("directivo", "secreto"))

    assert str(captured.value) == "La cuenta de usuario está inactiva."
    assert store.current is None


@pytest.mark.parametrize(
    ("auth_me_result", "expected_error"),
    [
        (httpx.Response(401), SessionExpiredError),
        (httpx.Response(403), AuthorizationError),
        (httpx.Response(503), ServiceUnavailableError),
        ("timeout", ApiTimeoutError),
        ("connection", ApiConnectionError),
    ],
)
def test_auth_me_failures_clear_the_pending_session(
    auth_me_result,
    expected_error,
):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/auth/login":
            return httpx.Response(
                200,
                json={
                    "access_token": "access-token",
                    "refresh_token": "refresh-token",
                },
            )
        if auth_me_result == "timeout":
            raise httpx.ReadTimeout("timeout", request=request)
        if auth_me_result == "connection":
            raise httpx.ConnectError("connection", request=request)
        return auth_me_result

    repository, store = repository_and_store(handler)

    with pytest.raises(expected_error):
        asyncio.run(repository.login("directivo", "secreto"))

    assert store.current is None


@pytest.mark.parametrize(
    "response_json",
    [
        {"refresh_token": "refresh-token"},
        {"access_token": "", "refresh_token": "refresh-token"},
        {"access_token": "access-token", "refresh_token": 123},
        ["access-token", "refresh-token"],
    ],
)
def test_api_login_rejects_unexpected_token_responses(response_json):
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=response_json)

    repository, store = repository_and_store(handler)

    with pytest.raises(UnexpectedResponseError):
        asyncio.run(repository.login("directivo", "secreto"))

    assert [request.url.path for request in requests] == ["/api/auth/login"]
    assert store.current is None


def test_invalid_login_clears_previous_session_and_never_calls_auth_me():
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(401, json={"detail": "invalid credentials"})

    repository, store = repository_and_store(handler)
    store.begin("old-access", "old-refresh")
    store.authenticate(authenticated_user())

    with pytest.raises(AuthenticationError):
        asyncio.run(repository.login("directivo", "incorrecta"))

    assert [request.url.path for request in requests] == ["/api/auth/login"]
    assert "Authorization" not in requests[0].headers
    assert store.current is None


def test_api_login_refreshes_once_when_the_pending_access_token_expires():
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/api/auth/login":
            return httpx.Response(
                200,
                json={
                    "access_token": "old-access",
                    "refresh_token": "old-refresh",
                },
            )
        if request.url.path == "/api/auth/refresh":
            assert "Authorization" not in request.headers
            assert json.loads(request.content) == {
                "refresh_token": "old-refresh"
            }
            return httpx.Response(
                200,
                json={
                    "access_token": "new-access",
                    "refresh_token": "new-refresh",
                },
            )
        if request.headers["Authorization"] == "Bearer old-access":
            return httpx.Response(401)
        assert request.headers["Authorization"] == "Bearer new-access"
        return httpx.Response(
            200,
            json={
                "id": 7,
                "username": "refreshed-user",
                "is_active": True,
                "is_admin": False,
            },
        )

    repository, store = repository_and_store(handler)

    session = asyncio.run(repository.login("directivo", "secreto"))

    assert [request.url.path for request in requests] == [
        "/api/auth/login",
        "/api/auth/me",
        "/api/auth/refresh",
        "/api/auth/me",
    ]
    assert session is store.current
    assert session.access_token == "new-access"
    assert session.refresh_token == "new-refresh"
    assert session.current_user is not None
    assert session.current_user.username == "refreshed-user"


@pytest.mark.parametrize(
    ("refresh_result", "expected_error"),
    [
        ("timeout", ApiTimeoutError),
        ("connection", ApiConnectionError),
        ("service-unavailable", ServiceUnavailableError),
    ],
)
def test_api_login_clears_the_pending_session_after_transient_refresh_failure(
    refresh_result,
    expected_error,
):
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/api/auth/login":
            return httpx.Response(
                200,
                json={
                    "access_token": "old-access",
                    "refresh_token": "old-refresh",
                },
            )
        if request.url.path == "/api/auth/me":
            return httpx.Response(401)
        if refresh_result == "timeout":
            raise httpx.ReadTimeout("slow refresh", request=request)
        if refresh_result == "connection":
            raise httpx.ConnectError("failed refresh", request=request)
        return httpx.Response(503)

    repository, store = repository_and_store(handler)

    with pytest.raises(expected_error):
        asyncio.run(repository.login("directivo", "secreto"))

    assert [request.url.path for request in requests] == [
        "/api/auth/login",
        "/api/auth/me",
        "/api/auth/refresh",
    ]
    assert store.current is None


def test_late_credentials_failure_does_not_clear_a_newer_login_session():
    async def scenario():
        first_login_started = asyncio.Event()
        release_first_login = asyncio.Event()

        async def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/api/auth/login":
                username = json.loads(request.content)["username"]
                if username == "first":
                    first_login_started.set()
                    await release_first_login.wait()
                    return httpx.Response(401)
                return httpx.Response(
                    200,
                    json={
                        "access_token": "second-access",
                        "refresh_token": "second-refresh",
                    },
                )
            assert request.headers["Authorization"] == "Bearer second-access"
            return httpx.Response(
                200,
                json={
                    "id": 2,
                    "username": "second",
                    "is_active": True,
                    "is_admin": False,
                },
            )

        repository, store = repository_and_store(handler)
        first_login = asyncio.create_task(
            repository.login("first", "secret")
        )
        await first_login_started.wait()

        second_session = await repository.login("second", "secret")
        release_first_login.set()

        with pytest.raises(AuthenticationError):
            await first_login

        assert store.current is second_session
        assert store.current.access_token == "second-access"
        assert store.current.refresh_token == "second-refresh"
        assert store.current.current_user is not None
        assert store.current.current_user.username == "second"

    asyncio.run(scenario())


def test_late_identity_failure_does_not_clear_a_newer_login_session():
    async def scenario():
        first_identity_started = asyncio.Event()
        release_first_identity = asyncio.Event()

        async def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/api/auth/login":
                username = json.loads(request.content)["username"]
                return httpx.Response(
                    200,
                    json={
                        "access_token": f"{username}-access",
                        "refresh_token": f"{username}-refresh",
                    },
                )
            authorization = request.headers["Authorization"]
            if authorization == "Bearer first-access":
                first_identity_started.set()
                await release_first_identity.wait()
                return httpx.Response(503)
            assert authorization == "Bearer second-access"
            return httpx.Response(
                200,
                json={
                    "id": 2,
                    "username": "second",
                    "is_active": True,
                    "is_admin": False,
                },
            )

        repository, store = repository_and_store(handler)
        first_login = asyncio.create_task(
            repository.login("first", "secret")
        )
        await first_identity_started.wait()

        second_session = await repository.login("second", "secret")
        release_first_identity.set()

        with pytest.raises(ServiceUnavailableError):
            await first_login

        assert store.current is second_session
        assert store.current.access_token == "second-access"
        assert store.current.refresh_token == "second-refresh"
        assert store.current.current_user is not None
        assert store.current.current_user.username == "second"

    asyncio.run(scenario())
