import asyncio

import httpx
import pytest

from esiqie_dictamenes.core.errors import (
    ApiConnectionError,
    ApiTimeoutError,
    NotFoundError,
    SessionExpiredError,
    UnexpectedResponseError,
)
from esiqie_dictamenes.core.settings import ApiSettings
from esiqie_dictamenes.infrastructure.http.api_client import ApiClient
from esiqie_dictamenes.infrastructure.http.inscrito_repository import (
    ApiInscritoRepository,
)
from esiqie_dictamenes.infrastructure.http.token_store import AuthTokenStore


INSCRITO_RESPONSE = {
    "Boleta": "2022630000",
    "Nombre": "María Hernández García",
    "Carrera": "Ingeniería Química Industrial",
    "Plan_estud": 2021,
    "Especialidad": "Procesos Industriales",
    "Secuencias": "5IM1",
    "Turno": "Matutino",
    "Genero": "Femenino",
    "Edad": 22,
    "Promedio": 8.51,
    "Dictamen_vigente": "NO",
    "Periodo_escolar_ingreso": "20221",
    "Periodos_cursados": 8,
    "Semestre_Nivel_Inscrito": 7,
    "No_cursadas": 1,
    "Reprobadas": 2,
    "Desfasadas": 0,
    "Periodo_en_que_reprobo": 20242,
    "Materias_inscritas": 6,
    "Materias_reprobadas_no_inscritas": 1,
    "Avance": 72.4,
    "Carga_minima": 24,
    "Carga_media": 36,
    "Carga_maxima": 48,
    "Total_de_Creditos_inscritos": 42,
    "Creditos_de_reprobadas_inscritas": 6,
    "Creditos_de_reprobadas_no_inscritas": 6,
    "Total_de_creditos": 310,
    "Posible_irregularidad": None,
}


def _repository(handler, *, with_token=True):
    settings = ApiSettings(
        "http://api.test",
        "/api/auth/login",
        "/api/inscritos/{boleta}",
        "/api/reprobados",
    )
    tokens = AuthTokenStore()
    if with_token:
        tokens.replace("access-token", "refresh-token")
    client = ApiClient(
        settings,
        tokens,
        transport=httpx.MockTransport(handler),
    )
    return ApiInscritoRepository(client, settings.inscrito_path), tokens


def test_inscrito_repository_gets_and_maps_the_complete_api_contract():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert str(request.url) == "http://api.test/api/inscritos/2022630000"
        assert request.headers["Authorization"] == "Bearer access-token"
        return httpx.Response(200, json=INSCRITO_RESPONSE)

    repository, _ = _repository(handler)

    alumno = asyncio.run(repository.get_inscrito("2022630000"))

    assert alumno.boleta == "2022630000"
    assert alumno.nombre == "María Hernández García"
    assert alumno.carrera == "Ingeniería Química Industrial"
    assert alumno.plan_estud == 2021
    assert alumno.especialidad == "Procesos Industriales"
    assert alumno.secuencias == "5IM1"
    assert alumno.turno == "Matutino"
    assert alumno.genero == "Femenino"
    assert alumno.edad == 22
    assert alumno.promedio == 8.51
    assert alumno.dictamen_vigente == "NO"
    assert alumno.periodo_escolar_ingreso == "20221"
    assert alumno.periodos_cursados == 8
    assert alumno.semestre_nivel_inscrito == 7
    assert alumno.no_cursadas == 1
    assert alumno.reprobadas == 2
    assert alumno.desfasadas == 0
    assert alumno.periodo_en_que_reprobo == 20242
    assert alumno.materias_inscritas == 6
    assert alumno.materias_reprobadas_no_inscritas == 1
    assert alumno.avance == 72.4
    assert alumno.carga_minima == 24
    assert alumno.carga_media == 36
    assert alumno.carga_maxima == 48
    assert alumno.creditos_inscritos == 42
    assert alumno.creditos_de_reprobadas_inscritas == 6
    assert alumno.creditos_de_reprobadas_no_inscritas == 6
    assert alumno.total_de_creditos == 310
    assert alumno.posible_irregularidad is None


def test_inscrito_repository_reports_a_student_specific_not_found_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"detail": "not found"})

    repository, _ = _repository(handler)

    with pytest.raises(NotFoundError, match="alumno inscrito"):
        asyncio.run(repository.get_inscrito("9999999999"))


def test_inscrito_repository_propagates_expired_sessions_and_clears_tokens():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"detail": "expired"})

    repository, tokens = _repository(handler)

    with pytest.raises(SessionExpiredError):
        asyncio.run(repository.get_inscrito("2022630000"))

    assert tokens.access_token is None


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (httpx.ReadTimeout("slow"), ApiTimeoutError),
        (httpx.ConnectError("offline"), ApiConnectionError),
    ],
)
def test_inscrito_repository_propagates_transport_errors(error, expected):
    def handler(request: httpx.Request) -> httpx.Response:
        error.request = request
        raise error

    repository, _ = _repository(handler)

    with pytest.raises(expected):
        asyncio.run(repository.get_inscrito("2022630000"))


@pytest.mark.parametrize(
    "response_json",
    [
        [INSCRITO_RESPONSE],
        {key: value for key, value in INSCRITO_RESPONSE.items() if key != "Nombre"},
        {**INSCRITO_RESPONSE, "Promedio": "8.51"},
        {**INSCRITO_RESPONSE, "Edad": "22"},
    ],
)
def test_inscrito_repository_rejects_unexpected_response_shapes(response_json):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=response_json)

    repository, _ = _repository(handler)

    with pytest.raises(UnexpectedResponseError):
        asyncio.run(repository.get_inscrito("2022630000"))
