import asyncio
import logging

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
from esiqie_dictamenes.core.session import AuthSessionStore
from esiqie_dictamenes.infrastructure.http.api_client import ApiClient
from esiqie_dictamenes.infrastructure.http.reprobado_repository import (
    ApiReprobadoRepository,
)
from tests.helpers import api_settings


REPROBADO_ITEM = {
    "Boleta": "2022630000",
    "Nombre": "NOMBRE DEL ALUMNO",
    "Turno": "MATUTINO",
    "E_Mail_Personal": None,
    "Carrera": "INGENIERIA QUIMICA INDUSTRIAL",
    "Plan_estud": 2021,
    "Materia": "TERMODINAMICA",
    "Departamento": "INGENIERIA QUIMICA INDUSTRIAL",
    "Academia": "TERMODINAMICA",
    "Periodo_reprobada": 20243,
    "Intentos_Ordinario": 2,
    "Intentos_ETS": 1,
    "Total_intentos": 3,
    "MateriaInscrita": "SI",
    "InscritoActualmente": None,
    "Tipo": None,
    "id": 123,
}


def paginated_response(*items):
    return {
        "total": len(items),
        "skip": 0,
        "limit": 100,
        "items": list(items),
    }


def _repository(handler, *, with_token=True):
    settings = api_settings()
    store = AuthSessionStore()
    if with_token:
        store.begin("access-secret", "refresh-secret")
    client = ApiClient(
        settings,
        store,
        transport=httpx.MockTransport(handler),
    )
    return ApiReprobadoRepository(client, settings.reprobado_path), store


def test_reprobado_repository_sends_boleta_as_query_and_maps_one_item():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/api/reprobados"
        assert request.url.params.get("boleta") == "2022630000"
        assert request.headers["Authorization"] == "Bearer access-secret"
        return httpx.Response(200, json=paginated_response(REPROBADO_ITEM))

    repository, _ = _repository(handler)

    result = asyncio.run(repository.search_reprobados(boleta="2022630000"))

    assert len(result) == 1
    assert result[0].boleta == "2022630000"
    assert result[0].nombre == "NOMBRE DEL ALUMNO"
    assert result[0].carrera == "INGENIERIA QUIMICA INDUSTRIAL"
    assert result[0].materia == "TERMODINAMICA"
    assert result[0].periodo_reprobada == 20243
    assert result[0].intentos_ordinario == 2
    assert result[0].materia_inscrita == "SI"
    assert not hasattr(result[0], "inscrito_actualmente")


@pytest.mark.parametrize("materia_inscrita", ["SI", "NO", None])
def test_reprobado_repository_preserves_materia_inscrita(materia_inscrita):
    item = {**REPROBADO_ITEM, "MateriaInscrita": materia_inscrita}
    repository, _ = _repository(
        lambda request: httpx.Response(200, json=paginated_response(item))
    )

    result = asyncio.run(repository.search_reprobados(boleta="2022630000"))

    assert result[0].materia_inscrita == materia_inscrita


def test_reprobado_repository_maps_multiple_items():
    second = {
        **REPROBADO_ITEM,
        "Materia": "CALCULO DIFERENCIAL",
        "Periodo_reprobada": 20252,
        "id": 124,
    }

    repository, _ = _repository(
        lambda request: httpx.Response(
            200, json=paginated_response(REPROBADO_ITEM, second)
        )
    )

    result = asyncio.run(repository.search_reprobados(boleta="2022630000"))

    assert [item.materia for item in result] == [
        "TERMODINAMICA",
        "CALCULO DIFERENCIAL",
    ]


def test_reprobado_repository_treats_an_empty_page_as_success():
    repository, _ = _repository(
        lambda request: httpx.Response(200, json=paginated_response())
    )

    result = asyncio.run(repository.search_reprobados(boleta="2022630000"))

    assert result == ()


def test_reprobado_repository_rejects_an_item_from_another_student():
    crossed_item = {**REPROBADO_ITEM, "Boleta": "9999999999"}
    repository, _ = _repository(
        lambda request: httpx.Response(
            200,
            json=paginated_response(crossed_item),
        )
    )

    with pytest.raises(UnexpectedResponseError):
        asyncio.run(repository.search_reprobados(boleta="2022630000"))


def test_reprobado_repository_rejects_inconsistent_common_student_data():
    conflicting_item = {
        **REPROBADO_ITEM,
        "Nombre": "OTRO ALUMNO",
        "Materia": "CALCULO DIFERENCIAL",
        "id": 124,
    }
    repository, _ = _repository(
        lambda request: httpx.Response(
            200,
            json=paginated_response(REPROBADO_ITEM, conflicting_item),
        )
    )

    with pytest.raises(UnexpectedResponseError):
        asyncio.run(repository.search_reprobados(boleta="2022630000"))


def test_reprobado_repository_rejects_a_partial_page():
    partial_page = {
        "total": 2,
        "skip": 0,
        "limit": 1,
        "items": [REPROBADO_ITEM],
    }
    repository, _ = _repository(
        lambda request: httpx.Response(200, json=partial_page)
    )

    with pytest.raises(UnexpectedResponseError):
        asyncio.run(repository.search_reprobados(boleta="2022630000"))


@pytest.mark.parametrize(
    ("status_code", "expected_error"),
    [
        (401, SessionExpiredError),
        (403, AuthorizationError),
        (422, ValidationError),
        (500, ServiceUnavailableError),
    ],
)
def test_reprobado_repository_propagates_controlled_http_errors(
    status_code, expected_error
):
    repository, _ = _repository(
        lambda request: httpx.Response(status_code, json={"detail": "error"})
    )

    with pytest.raises(expected_error):
        asyncio.run(repository.search_reprobados(boleta="2022630000"))


def test_reprobado_repository_clears_the_session_only_on_401():
    repository, store = _repository(
        lambda request: httpx.Response(401, json={"detail": "expired"})
    )

    with pytest.raises(SessionExpiredError):
        asyncio.run(repository.search_reprobados(boleta="2022630000"))

    assert store.current is None


def test_reprobado_repository_keeps_the_session_on_403():
    repository, store = _repository(
        lambda request: httpx.Response(403, json={"detail": "inactive"})
    )

    with pytest.raises(AuthorizationError):
        asyncio.run(repository.search_reprobados(boleta="2022630000"))

    assert store.access_token == "access-secret"
    assert store.current is not None


@pytest.mark.parametrize(
    ("transport_error", "expected_error"),
    [
        (httpx.ReadTimeout("slow"), ApiTimeoutError),
        (httpx.ConnectError("offline"), ApiConnectionError),
    ],
)
def test_reprobado_repository_propagates_transport_errors(
    transport_error, expected_error
):
    def handler(request: httpx.Request) -> httpx.Response:
        transport_error.request = request
        raise transport_error

    repository, _ = _repository(handler)

    with pytest.raises(expected_error):
        asyncio.run(repository.search_reprobados(boleta="2022630000"))


def test_reprobado_repository_rejects_non_json_responses():
    repository, _ = _repository(
        lambda request: httpx.Response(200, text="not-json")
    )

    with pytest.raises(UnexpectedResponseError):
        asyncio.run(repository.search_reprobados(boleta="2022630000"))


@pytest.mark.parametrize(
    "response_json",
    [
        [REPROBADO_ITEM],
        {"total": 1, "skip": 0, "limit": 100},
        {"total": "1", "skip": 0, "limit": 100, "items": [REPROBADO_ITEM]},
        {"total": 1, "skip": 0, "limit": 100, "items": REPROBADO_ITEM},
    ],
)
def test_reprobado_repository_rejects_malformed_pages(response_json):
    repository, _ = _repository(
        lambda request: httpx.Response(200, json=response_json)
    )

    with pytest.raises(UnexpectedResponseError):
        asyncio.run(repository.search_reprobados(boleta="2022630000"))


@pytest.mark.parametrize(
    "item",
    [
        {key: value for key, value in REPROBADO_ITEM.items() if key != "Materia"},
        {**REPROBADO_ITEM, "Plan_estud": "2021"},
        {key: value for key, value in REPROBADO_ITEM.items() if key != "Intentos_Ordinario"},
        {**REPROBADO_ITEM, "Intentos_Ordinario": "2"},
        {**REPROBADO_ITEM, "Intentos_ETS": "1"},
        {**REPROBADO_ITEM, "MateriaInscrita": 123},
        {**REPROBADO_ITEM, "E_Mail_Personal": 123},
    ],
)
def test_reprobado_repository_rejects_invalid_items(item):
    repository, _ = _repository(
        lambda request: httpx.Response(200, json=paginated_response(item))
    )

    with pytest.raises(UnexpectedResponseError):
        asyncio.run(repository.search_reprobados(boleta="2022630000"))


def test_reprobado_repository_requires_a_boleta():
    repository, _ = _repository(
        lambda request: pytest.fail("Invalid input must not call the API.")
    )

    with pytest.raises(ValidationError, match="boleta"):
        asyncio.run(repository.search_reprobados(nombre="Ana"))


def test_reprobado_repository_never_logs_boleta_or_tokens(caplog):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    repository, _ = _repository(handler)

    with caplog.at_level(logging.WARNING), pytest.raises(ApiTimeoutError):
        asyncio.run(repository.search_reprobados(boleta="2022630000"))

    assert "API request timed out" in caplog.text
    assert "2022630000" not in caplog.text
    assert "access-secret" not in caplog.text
    assert "refresh-secret" not in caplog.text
