import asyncio
import json
import logging

import httpx
import pytest

from esiqie_dictamenes.core.errors import (
    ApiTimeoutError,
    AuthorizationError,
    ServiceUnavailableError,
    UnexpectedResponseError,
    ValidationError,
)
from esiqie_dictamenes.infrastructure.http.api_client import ApiClient
from esiqie_dictamenes.infrastructure.http.user_repository import ApiUserRepository
from tests.helpers import api_settings, authenticated_store


REGISTER_RESPONSE = {
    "message": "Usuario creado correctamente",
    "created_by": "directivo",
    "user": {
        "id": 9,
        "username": "nuevo",
        "is_active": True,
        "is_admin": False,
        "created_at": "2026-08-29T12:34:56",
    },
}


def repository_and_store(handler):
    store = authenticated_store()
    client = ApiClient(
        api_settings(),
        store,
        transport=httpx.MockTransport(handler),
    )
    return ApiUserRepository(client, "/api/auth/register"), store


def test_api_user_repository_posts_the_exact_contract_and_maps_registered_user():
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(201, json=REGISTER_RESPONSE)

    repository, _ = repository_and_store(handler)

    user = asyncio.run(repository.register("nuevo", "dummy123", False))

    assert user.username == "nuevo"
    assert user.is_admin is False
    assert len(requests) == 1
    assert requests[0].method == "POST"
    assert requests[0].url.path == "/api/auth/register"
    assert requests[0].headers["Authorization"] == "Bearer access-secret"
    assert json.loads(requests[0].content) == {
        "username": "nuevo",
        "password": "dummy123",
        "is_admin": False,
    }


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {key: value for key, value in REGISTER_RESPONSE.items() if key != "message"},
        {**REGISTER_RESPONSE, "created_by": " "},
        {**REGISTER_RESPONSE, "user": []},
        {**REGISTER_RESPONSE, "user": {**REGISTER_RESPONSE["user"], "id": True}},
        {
            **REGISTER_RESPONSE,
            "user": {**REGISTER_RESPONSE["user"], "username": "otro"},
        },
        {
            **REGISTER_RESPONSE,
            "user": {**REGISTER_RESPONSE["user"], "is_active": False},
        },
        {
            **REGISTER_RESPONSE,
            "user": {**REGISTER_RESPONSE["user"], "is_admin": True},
        },
        {
            **REGISTER_RESPONSE,
            "user": {**REGISTER_RESPONSE["user"], "created_at": "not-a-date"},
        },
    ],
)
def test_api_user_repository_rejects_malformed_or_mismatched_success(payload):
    repository, _ = repository_and_store(
        lambda _request: httpx.Response(201, json=payload)
    )

    with pytest.raises(UnexpectedResponseError):
        asyncio.run(repository.register("nuevo", "dummy123", False))


def test_api_user_repository_maps_the_confirmed_duplicate_username_detail():
    repository, _ = repository_and_store(
        lambda _request: httpx.Response(
            400,
            json={"detail": "El nombre de usuario ya existe"},
        )
    )

    with pytest.raises(ValidationError, match="nombre de usuario ya existe"):
        asyncio.run(repository.register("nuevo", "dummy123", False))


def test_api_user_repository_preserves_session_and_does_not_refresh_on_403():
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(403, json={"detail": "No tienes permisos suficientes"})

    repository, store = repository_and_store(handler)
    session = store.current

    with pytest.raises(AuthorizationError):
        asyncio.run(repository.register("nuevo", "dummy123", False))

    assert requests[0].url.path == "/api/auth/register"
    assert len(requests) == 1
    assert store.current is session


def test_api_user_repository_uses_central_refresh_and_one_replay_on_401():
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/api/auth/refresh":
            assert "Authorization" not in request.headers
            return httpx.Response(
                200,
                json={
                    "access_token": "new-access",
                    "refresh_token": "new-refresh",
                },
            )
        if request.headers["Authorization"] == "Bearer access-secret":
            return httpx.Response(401, json={"detail": "Token expirado"})
        return httpx.Response(201, json=REGISTER_RESPONSE)

    repository, store = repository_and_store(handler)

    user = asyncio.run(repository.register("nuevo", "dummy123", False))

    assert user.username == "nuevo"
    assert [(request.method, request.url.path) for request in requests] == [
        ("POST", "/api/auth/register"),
        ("POST", "/api/auth/refresh"),
        ("POST", "/api/auth/register"),
    ]
    assert store.access_token == "new-access"
    assert store.refresh_token == "new-refresh"


@pytest.mark.parametrize(
    ("status_code", "error_type"),
    [
        (422, ValidationError),
        (503, ServiceUnavailableError),
    ],
)
def test_api_user_repository_reuses_central_status_mapping(status_code, error_type):
    repository, _ = repository_and_store(
        lambda _request: httpx.Response(status_code, json={"detail": "internal"})
    )

    with pytest.raises(error_type):
        asyncio.run(repository.register("nuevo", "dummy123", False))


def test_api_user_repository_never_exposes_password_in_repr_logs_or_errors(caplog):
    secret = "fictional-password"

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    repository, _ = repository_and_store(handler)

    with caplog.at_level(logging.WARNING):
        with pytest.raises(ApiTimeoutError) as raised:
            asyncio.run(repository.register("nuevo", secret, False))

    assert secret not in repr(repository)
    assert secret not in caplog.text
    assert secret not in repr(raised.value)
