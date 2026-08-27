import asyncio
import json

import httpx
import pytest

from esiqie_dictamenes.core.errors import (
    AuthenticationError,
    UnexpectedResponseError,
)
from esiqie_dictamenes.core.settings import ApiSettings
from esiqie_dictamenes.infrastructure.http.api_client import ApiClient
from esiqie_dictamenes.infrastructure.http.auth_repository import ApiAuthRepository
from esiqie_dictamenes.infrastructure.http.token_store import AuthTokenStore


def _repository(handler):
    settings = ApiSettings(
        "http://api.test",
        "/api/auth/login",
        "/api/inscritos/{boleta}",
        "/api/reprobados",
        "/api/dictaminaciones",
        "/api/dictaminaciones",
        "/api/dictaminaciones/{clave}",
        "/api/dictaminaciones/bulk",
    )
    tokens = AuthTokenStore()
    client = ApiClient(
        settings,
        tokens,
        transport=httpx.MockTransport(handler),
    )
    return ApiAuthRepository(client, tokens, settings.login_path), tokens


def test_api_login_creates_session_and_stores_tokens():
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "http://api.test/api/auth/login"
        assert request.method == "POST"
        assert "Authorization" not in request.headers
        assert json.loads(request.content) == {
            "username": "directivo",
            "password": "secreto",
        }
        return httpx.Response(
            200,
            json={
                "access_token": "access-token",
                "refresh_token": "refresh-token",
                "token_type": "bearer",
            },
        )

    repository, tokens = _repository(handler)

    session = asyncio.run(repository.login("directivo", "secreto"))

    assert session.username == "directivo"
    assert session.is_admin is False
    assert session.is_demo is False
    assert tokens.access_token == "access-token"


@pytest.mark.parametrize(
    "response_json",
    [
        {
            "refresh_token": "refresh-token",
            "token_type": "bearer",
        },
        {
            "access_token": "",
            "refresh_token": "refresh-token",
            "token_type": "bearer",
        },
        {
            "access_token": "access-token",
            "refresh_token": 123,
            "token_type": "bearer",
        },
        ["access-token", "refresh-token"],
    ],
)
def test_api_login_rejects_unexpected_token_responses(response_json):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=response_json)

    repository, tokens = _repository(handler)

    with pytest.raises(UnexpectedResponseError):
        asyncio.run(repository.login("directivo", "secreto"))

    assert tokens.access_token is None


def test_failed_login_clears_previous_tokens_before_the_request():
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(
                200,
                json={
                    "access_token": "old-access",
                    "refresh_token": "old-refresh",
                    "token_type": "bearer",
                },
            )
        assert "Authorization" not in request.headers
        return httpx.Response(401, json={"detail": "invalid credentials"})

    repository, tokens = _repository(handler)
    asyncio.run(repository.login("directivo", "secreto"))

    with pytest.raises(AuthenticationError):
        asyncio.run(repository.login("directivo", "incorrecta"))

    assert tokens.access_token is None
