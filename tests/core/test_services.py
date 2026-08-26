import asyncio
from datetime import date

import httpx
import pytest

from esiqie_dictamenes.core.services import build_demo_services, build_services
from esiqie_dictamenes.core.settings import ApiSettings
from esiqie_dictamenes.features.dictamenes.models import DictamenFilter
from tests.infrastructure.http.test_inscrito_repository import INSCRITO_RESPONSE
from tests.infrastructure.http.test_reprobado_repository import (
    REPROBADO_ITEM,
    paginated_response,
)
from tests.infrastructure.http.test_dictamen_repository import CREATED_RESPONSE


def test_demo_services_do_not_share_mutable_repositories_between_sessions():
    first = build_demo_services()
    second = build_demo_services()

    assert first.dictamen_repository is not second.dictamen_repository
    assert first.auth_repository is not second.auth_repository
    assert first.auth_tokens is not second.auth_tokens


def test_production_services_use_api_login_and_store_tokens():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "access_token": "access-token",
                "refresh_token": "refresh-token",
                "token_type": "bearer",
            },
        )

    services = build_services(
        settings=ApiSettings(
            "http://api.test",
            "/api/auth/login",
            "/api/inscritos/{boleta}",
            "/api/reprobados",
            "/api/dictaminaciones",
        ),
        transport=httpx.MockTransport(handler),
    )

    session = asyncio.run(
        services.auth_controller.login("directivo", "secreto")
    )

    assert session.is_demo is False
    assert services.auth_tokens.access_token == "access-token"


def test_production_services_keep_user_registration_in_demo_mode():
    def reject_network(request: httpx.Request) -> httpx.Response:
        raise AssertionError("User registration must not call the API yet.")

    services = build_services(
        settings=ApiSettings(
            "http://api.test",
            "/api/auth/login",
            "/api/inscritos/{boleta}",
            "/api/reprobados",
            "/api/dictaminaciones",
        ),
        transport=httpx.MockTransport(reject_network),
    )

    user = asyncio.run(
        services.user_controller.register(
            "nuevo",
            "secreto",
            "secreto",
            True,
        )
    )

    assert user.username == "nuevo"
    assert user.is_admin is True


def test_services_clear_tokens_on_logout():
    services = build_demo_services()
    services.auth_tokens.replace("access-token", "refresh-token")

    services.clear_authentication()

    assert services.auth_tokens.access_token is None


def test_production_services_share_login_token_with_inscritos():
    paths = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        if request.url.path == "/api/auth/login":
            return httpx.Response(
                200,
                json={
                    "access_token": "shared-access",
                    "refresh_token": "shared-refresh",
                    "token_type": "bearer",
                },
            )
        assert request.url.path == "/api/inscritos/2022630000"
        assert request.headers["Authorization"] == "Bearer shared-access"
        return httpx.Response(200, json=INSCRITO_RESPONSE)

    services = build_services(
        settings=ApiSettings(
            "http://api.test",
            "/api/auth/login",
            "/api/inscritos/{boleta}",
            "/api/reprobados",
            "/api/dictaminaciones",
        ),
        transport=httpx.MockTransport(handler),
    )
    asyncio.run(services.auth_controller.login("directivo", "secreto"))

    candidate = asyncio.run(
        services.dictamen_controller.find_student_candidate(
            "inscrito",
            " 2022630000 ",
            "20262",
        )
    )

    assert candidate.alumno.nombre == "María Hernández García"
    assert paths == ["/api/auth/login", "/api/inscritos/2022630000"]


def test_production_services_share_login_token_with_reprobados():
    paths = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        if request.url.path == "/api/auth/login":
            return httpx.Response(
                200,
                json={
                    "access_token": "shared-access",
                    "refresh_token": "shared-refresh",
                    "token_type": "bearer",
                },
            )
        assert request.url.path == "/api/reprobados"
        assert request.url.params.get("boleta") == "2022630000"
        assert request.headers["Authorization"] == "Bearer shared-access"
        return httpx.Response(200, json=paginated_response(REPROBADO_ITEM))

    services = build_services(
        settings=ApiSettings(
            "http://api.test",
            "/api/auth/login",
            "/api/inscritos/{boleta}",
            "/api/reprobados",
            "/api/dictaminaciones",
        ),
        transport=httpx.MockTransport(handler),
    )
    asyncio.run(services.auth_controller.login("directivo", "secreto"))

    candidate = asyncio.run(
        services.dictamen_controller.find_student_candidate(
            "reprobado",
            "2022630000",
            "20262",
        )
    )

    assert candidate.alumno.nombre == "NOMBRE DEL ALUMNO"
    assert candidate.total_reprobadas == 1
    assert [item.materia for item in candidate.materias] == ["TERMODINAMICA"]
    assert paths == ["/api/auth/login", "/api/reprobados"]


def test_production_services_create_rulings_through_the_api_only():
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/api/auth/login":
            return httpx.Response(
                200,
                json={
                    "access_token": "shared-access",
                    "refresh_token": "shared-refresh",
                    "token_type": "bearer",
                },
            )
        if request.url.path == "/api/inscritos/2022630000":
            return httpx.Response(200, json=INSCRITO_RESPONSE)
        assert request.url.path == "/api/dictaminaciones"
        assert request.headers["Authorization"] == "Bearer shared-access"
        return httpx.Response(201, json=CREATED_RESPONSE)

    services = build_services(
        settings=ApiSettings(
            "http://api.test",
            "/api/auth/login",
            "/api/inscritos/{boleta}",
            "/api/reprobados",
            "/api/dictaminaciones",
        ),
        transport=httpx.MockTransport(handler),
    )
    asyncio.run(services.auth_controller.login("directivo", "secreto"))
    alumno = asyncio.run(
        services.alumno_controller.find_inscrito("2022630000")
    )

    result = asyncio.run(
        services.dictamen_controller.create(
            alumno=alumno,
            dictaminacion="CONTENIDO CONFIDENCIAL DEL DICTAMEN",
            director="Dr. Dirección Escolar",
            materias=(),
            reference=date(2026, 8, 26),
            fecha_sesion=date(2026, 12, 11),
        )
    )

    assert result.dictamen.clave == "CSE-0001-26"
    assert [request.method for request in requests] == ["POST", "GET", "POST"]


def test_production_services_keep_ruling_reads_in_demo_mode():
    services = build_services(
        settings=ApiSettings(
            "http://api.test",
            "/api/auth/login",
            "/api/inscritos/{boleta}",
            "/api/reprobados",
            "/api/dictaminaciones",
        ),
        transport=httpx.MockTransport(
            lambda request: pytest.fail("Demo reads must not call the API.")
        ),
    )

    records = asyncio.run(
        services.dictamen_controller.search(DictamenFilter(anio=2025))
    )

    assert records
