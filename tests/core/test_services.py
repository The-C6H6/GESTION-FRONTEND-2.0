import asyncio
from datetime import date

import httpx
import pytest

from esiqie_dictamenes.core.services import build_demo_services, build_services
from esiqie_dictamenes.features.dictamenes.models import Dictamen, DictamenFilter
from tests.helpers import api_settings
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
        settings=api_settings(),
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
        settings=api_settings(),
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
        settings=api_settings(),
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
        settings=api_settings(),
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
        settings=api_settings(),
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


def test_production_services_search_rulings_through_the_shared_api_client():
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
        assert request.url.path == "/api/dictaminaciones"
        assert request.headers["Authorization"] == "Bearer shared-access"
        assert request.url.query == b"anio=2026&skip=0&limit=100"
        return httpx.Response(
            200,
            json={
                "total": 1,
                "skip": 0,
                "limit": 100,
                "items": [CREATED_RESPONSE],
            },
        )

    services = build_services(
        settings=api_settings(),
        transport=httpx.MockTransport(handler),
    )
    asyncio.run(services.auth_controller.login("directivo", "secreto"))

    result = asyncio.run(
        services.dictamen_controller.search_page(
            DictamenFilter(anio=2026),
            page=1,
        )
    )

    assert result.total == 1
    assert result.items[0].clave == "CSE-0001-26"
    assert paths == ["/api/auth/login", "/api/dictaminaciones"]


def test_production_services_update_rulings_through_the_shared_api_client():
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
        assert request.method == "PUT"
        assert request.url.path == "/custom/dictaminaciones/CSE-0001-26"
        assert request.headers["Authorization"] == "Bearer shared-access"
        assert request.content == b'{"Dictaminacion":"DICTAMEN ACTUALIZADO"}'
        updated = {**CREATED_RESPONSE, "Dictaminacion": "DICTAMEN ACTUALIZADO"}
        return httpx.Response(200, json=updated)

    services = build_services(
        settings=api_settings(
            dictamen_update_path="/custom/dictaminaciones/{clave}"
        ),
        transport=httpx.MockTransport(handler),
    )
    asyncio.run(services.auth_controller.login("directivo", "secreto"))
    current = Dictamen(
        clave="CSE-0001-26",
        boleta=CREATED_RESPONSE["Boleta"],
        alumno=CREATED_RESPONSE["Nombre"],
        fecha=date.fromisoformat(CREATED_RESPONSE["Fecha"]),
        anio=2026,
        dictaminacion=CREATED_RESPONSE["Dictaminacion"],
    )

    updated = asyncio.run(
        services.dictamen_controller.update_dictaminacion(
            current,
            "DICTAMEN ACTUALIZADO",
        )
    )

    assert updated.dictaminacion == "DICTAMEN ACTUALIZADO"
    assert [request.method for request in requests] == ["POST", "PUT"]


def test_production_services_delete_rulings_through_the_shared_api_client():
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
        assert request.method == "DELETE"
        assert request.url.path == "/custom/dictaminaciones/bulk"
        assert request.headers["Authorization"] == "Bearer shared-access"
        assert request.content == b'{"claves":["CSE-0001-26"]}'
        return httpx.Response(
            200,
            json={
                "message": "Dictaminacion eliminada",
                "total": 1,
                "claves": ["CSE-0001-26"],
            },
        )

    services = build_services(
        settings=api_settings(
            dictamen_delete_path="/custom/dictaminaciones/bulk"
        ),
        transport=httpx.MockTransport(handler),
    )
    asyncio.run(services.auth_controller.login("directivo", "secreto"))
    current = Dictamen(
        clave="CSE-0001-26",
        boleta=CREATED_RESPONSE["Boleta"],
        alumno=CREATED_RESPONSE["Nombre"],
        fecha=date.fromisoformat(CREATED_RESPONSE["Fecha"]),
        anio=2026,
        dictaminacion=CREATED_RESPONSE["Dictaminacion"],
    )

    total = asyncio.run(
        services.dictamen_controller.delete_dictamenes((current,))
    )

    assert total == 1
    assert [request.method for request in requests] == ["POST", "DELETE"]
