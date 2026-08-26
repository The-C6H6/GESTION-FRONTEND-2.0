import asyncio
import json
import logging
from datetime import date

import httpx
import pytest

from esiqie_dictamenes.core.errors import (
    ApiConnectionError,
    ApiTimeoutError,
    AuthorizationError,
    ServiceUnavailableError,
    SessionExpiredError,
    UnexpectedResponseError,
    ValidationError,
)
from esiqie_dictamenes.core.settings import ApiSettings
from esiqie_dictamenes.features.dictamenes.models import DictamenCreate, DictamenFilter
from esiqie_dictamenes.infrastructure.http.api_client import ApiClient
from esiqie_dictamenes.infrastructure.http.dictamen_repository import (
    ApiDictamenRepository,
)
from esiqie_dictamenes.infrastructure.http.token_store import AuthTokenStore


CREATE_PAYLOAD = DictamenCreate(
    boleta="2022630000",
    nombre="NOMBRE DEL ALUMNO",
    fecha=date(2026, 8, 26),
    anio=2026,
    dictaminacion="CONTENIDO CONFIDENCIAL DEL DICTAMEN",
)

CREATED_RESPONSE = {
    "Boleta": "2022630000",
    "Nombre": "NOMBRE DEL ALUMNO",
    "Fecha": "2026-08-26",
    "Anio": 2026,
    "Dictaminacion": "CONTENIDO CONFIDENCIAL DEL DICTAMEN",
    "Clave": "CSE-0001-26",
}

SEARCH_ITEM = {
    "Boleta": "2022630000",
    "Nombre": "NOMBRE DEL ALUMNO",
    "Fecha": "2026-08-26",
    "Anio": 2026,
    "Dictaminacion": "CONTENIDO CONFIDENCIAL DEL DICTAMEN",
    "Clave": "CSE-0001-26",
}


def search_page(*items, total=None, skip=0, limit=100):
    return {
        "total": len(items) if total is None else total,
        "skip": skip,
        "limit": limit,
        "items": list(items),
    }


def _repository(handler):
    settings = ApiSettings(
        "http://api.test",
        "/api/auth/login",
        "/api/inscritos/{boleta}",
        "/api/reprobados",
        "/api/dictaminaciones",
        "/api/dictaminaciones",
    )
    tokens = AuthTokenStore()
    tokens.replace("access-secret", "refresh-secret")
    client = ApiClient(
        settings,
        tokens,
        transport=httpx.MockTransport(handler),
    )
    return (
        ApiDictamenRepository(
            client,
            settings.dictamen_create_path,
            settings.dictamen_search_path,
        ),
        tokens,
    )


@pytest.mark.parametrize(
    ("filters", "skip", "expected_query"),
    [
        (
            DictamenFilter(boleta="2022630000"),
            0,
            "boleta=2022630000&skip=0&limit=100",
        ),
        (DictamenFilter(anio=2026), 100, "anio=2026&skip=100&limit=100"),
    ],
)
def test_search_sends_exact_filter_and_pagination_parameters(
    filters,
    skip,
    expected_query,
):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/api/dictaminaciones"
        assert request.url.query.decode() == expected_query
        assert request.headers["Authorization"] == "Bearer access-secret"
        return httpx.Response(
            200,
            json=search_page(SEARCH_ITEM, total=101, skip=skip),
        )

    repository, _ = _repository(handler)

    result = asyncio.run(repository.search_page(filters, skip=skip, limit=100))

    assert result.total == 101
    assert result.skip == skip
    assert result.limit == 100
    assert len(result.items) == 1
    assert result.items[0].fecha == date(2026, 8, 26)
    assert result.items[0].clave == "CSE-0001-26"


def test_search_maps_the_known_empty_400_to_an_empty_page_only():
    repository, _ = _repository(
        lambda request: httpx.Response(
            400,
            json={
                "detail": (
                    "No se encontraron dictaminaciones con los datos "
                    "proporcionados."
                )
            },
        )
    )

    result = asyncio.run(
        repository.search_page(
            DictamenFilter(boleta="2022630000"),
            skip=0,
            limit=100,
        )
    )

    assert result.total == 0
    assert result.items == ()


def test_search_preserves_unrelated_400_as_validation_error():
    repository, _ = _repository(
        lambda request: httpx.Response(
            400,
            json={"detail": "El filtro no estÃ¡ permitido."},
        )
    )

    with pytest.raises(ValidationError):
        asyncio.run(
            repository.search_page(
                DictamenFilter(anio=2026),
                skip=0,
                limit=100,
            )
        )


@pytest.mark.parametrize(
    "response_json",
    [
        [],
        {"total": 0, "skip": 0, "limit": 100},
        search_page(total=-1),
        search_page(total=0, skip=-1),
        search_page(total=0, limit=0),
        search_page(SEARCH_ITEM, total=1, limit=1),
        search_page(SEARCH_ITEM, total=0),
        search_page({**SEARCH_ITEM, "Fecha": "26 DE AGOSTO"}),
        search_page({**SEARCH_ITEM, "Anio": "2026"}),
        search_page({key: value for key, value in SEARCH_ITEM.items() if key != "Clave"}),
    ],
)
def test_search_rejects_a_malformed_paginated_contract(response_json):
    repository, _ = _repository(
        lambda request: httpx.Response(200, json=response_json)
    )

    with pytest.raises(UnexpectedResponseError):
        asyncio.run(
            repository.search_page(
                DictamenFilter(boleta="2022630000"),
                skip=0,
                limit=100,
            )
        )


@pytest.mark.parametrize(
    ("status_code", "expected_error"),
    [
        (401, SessionExpiredError),
        (403, AuthorizationError),
        (422, ValidationError),
        (500, ServiceUnavailableError),
    ],
)
def test_search_propagates_controlled_http_errors(status_code, expected_error):
    repository, _ = _repository(
        lambda request: httpx.Response(status_code, json={"detail": "error"})
    )

    with pytest.raises(expected_error):
        asyncio.run(
            repository.search_page(
                DictamenFilter(anio=2026),
                skip=0,
                limit=100,
            )
        )


def test_create_sends_the_exact_api_payload_and_maps_the_created_ruling():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/api/dictaminaciones"
        assert request.headers["Authorization"] == "Bearer access-secret"
        assert json.loads(request.content) == {
            "Boleta": "2022630000",
            "Nombre": "NOMBRE DEL ALUMNO",
            "Fecha": "2026-08-26",
            "Anio": 2026,
            "Dictaminacion": "CONTENIDO CONFIDENCIAL DEL DICTAMEN",
        }
        assert "Clave" not in json.loads(request.content)
        return httpx.Response(201, json=CREATED_RESPONSE)

    repository, _ = _repository(handler)

    result = asyncio.run(repository.create(CREATE_PAYLOAD))

    assert result.clave == "CSE-0001-26"
    assert result.boleta == "2022630000"
    assert result.alumno == "NOMBRE DEL ALUMNO"
    assert result.fecha == date(2026, 8, 26)
    assert result.anio == 2026
    assert result.dictaminacion == "CONTENIDO CONFIDENCIAL DEL DICTAMEN"


def test_create_rejects_a_200_response_even_when_its_payload_is_valid():
    repository, _ = _repository(
        lambda request: httpx.Response(200, json=CREATED_RESPONSE)
    )

    with pytest.raises(UnexpectedResponseError):
        asyncio.run(repository.create(CREATE_PAYLOAD))


@pytest.mark.parametrize(
    "response_json",
    [
        [CREATED_RESPONSE],
        {key: value for key, value in CREATED_RESPONSE.items() if key != "Clave"},
        {**CREATED_RESPONSE, "Clave": 123},
        {**CREATED_RESPONSE, "Anio": "2026"},
        {**CREATED_RESPONSE, "Fecha": 20260826},
        {**CREATED_RESPONSE, "Fecha": "26 DE AGOSTO"},
        {**CREATED_RESPONSE, "Boleta": None},
        {**CREATED_RESPONSE, "Dictaminacion": None},
    ],
)
def test_create_rejects_an_invalid_response_contract(response_json):
    repository, _ = _repository(
        lambda request: httpx.Response(201, json=response_json)
    )

    with pytest.raises(UnexpectedResponseError):
        asyncio.run(repository.create(CREATE_PAYLOAD))


def test_create_rejects_invalid_json():
    repository, _ = _repository(
        lambda request: httpx.Response(201, text="not-json")
    )

    with pytest.raises(UnexpectedResponseError):
        asyncio.run(repository.create(CREATE_PAYLOAD))


@pytest.mark.parametrize(
    ("status_code", "expected_error"),
    [
        (400, ValidationError),
        (401, SessionExpiredError),
        (403, AuthorizationError),
        (422, ValidationError),
        (500, ServiceUnavailableError),
    ],
)
def test_create_propagates_controlled_http_errors(status_code, expected_error):
    repository, _ = _repository(
        lambda request: httpx.Response(status_code, json={"detail": "error"})
    )

    with pytest.raises(expected_error):
        asyncio.run(repository.create(CREATE_PAYLOAD))


def test_create_clears_both_tokens_on_401():
    repository, tokens = _repository(
        lambda request: httpx.Response(401, json={"detail": "expired"})
    )

    with pytest.raises(SessionExpiredError):
        asyncio.run(repository.create(CREATE_PAYLOAD))

    assert tokens.has_tokens is False


@pytest.mark.parametrize(
    ("transport_error", "expected_error"),
    [
        (httpx.ReadTimeout("slow"), ApiTimeoutError),
        (httpx.ConnectError("offline"), ApiConnectionError),
    ],
)
def test_create_does_not_retry_ambiguous_transport_failures(
    transport_error,
    expected_error,
):
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        transport_error.request = request
        raise transport_error

    repository, _ = _repository(handler)

    with pytest.raises(expected_error):
        asyncio.run(repository.create(CREATE_PAYLOAD))

    assert attempts == 1


@pytest.mark.parametrize("failure", ["timeout", "invalid_json"])
def test_create_never_logs_payload_or_credentials(failure, caplog):
    def handler(request: httpx.Request) -> httpx.Response:
        if failure == "timeout":
            raise httpx.ReadTimeout("slow", request=request)
        return httpx.Response(201, text="not-json")

    repository, _ = _repository(handler)

    with caplog.at_level(logging.WARNING), pytest.raises(
        (ApiTimeoutError, UnexpectedResponseError)
    ):
        asyncio.run(repository.create(CREATE_PAYLOAD))

    assert "2022630000" not in caplog.text
    assert "NOMBRE DEL ALUMNO" not in caplog.text
    assert "access-secret" not in caplog.text
    assert "refresh-secret" not in caplog.text
    assert "CONTENIDO CONFIDENCIAL DEL DICTAMEN" not in caplog.text

