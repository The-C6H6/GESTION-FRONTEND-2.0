import asyncio
import json
from datetime import date

import httpx
import pytest

from esiqie_dictamenes.core.errors import AuthorizationError
from esiqie_dictamenes.core.services import build_services
from esiqie_dictamenes.features.dictamenes.models import (
    Dictamen,
    DictamenFilter,
    GeneratedDocument,
    PdfRequest,
)
from esiqie_dictamenes.infrastructure.pdf.document_store import LocalPdfDocumentStore
from esiqie_dictamenes.infrastructure.pdf.generator import RealPdfGenerator
from tests.helpers import (
    RecordingPdfDocumentStore,
    RecordingPdfGenerator,
    api_settings,
    build_test_services,
)
from tests.infrastructure.http.test_inscrito_repository import INSCRITO_RESPONSE
from tests.infrastructure.http.test_reprobado_repository import (
    REPROBADO_ITEM,
    paginated_response,
)
from tests.infrastructure.http.test_dictamen_repository import CREATED_RESPONSE
from tests.infrastructure.http.test_user_repository import REGISTER_RESPONSE


AUTH_ME_RESPONSE = {
    "id": 7,
    "username": "identity-from-api",
    "is_active": True,
    "is_admin": True,
}


def test_test_services_do_not_share_mutable_state_between_sessions():
    first = build_test_services()
    second = build_test_services()

    assert first.dictamen_repository is not second.dictamen_repository
    assert first.auth_repository is not second.auth_repository
    assert first.auth_session is not second.auth_session
    assert first.document_store is not second.document_store


def test_test_services_inject_fake_pdf_collaborators_without_local_writes():
    document = GeneratedDocument(
        filename="fake.pdf",
        content=b"%PDF-test",
        is_simulation=False,
    )
    pdf_generator = RecordingPdfGenerator(document)
    document_store = RecordingPdfDocumentStore("memory-output.pdf")
    services = build_test_services(
        pdf_generator=pdf_generator,
        document_store=document_store,
    )
    request = PdfRequest(
        dictamen=Dictamen(
            "D-00132",
            "2024320678",
            "Ana L\u00f3pez Mart\u00ednez",
            date(2026, 8, 30),
            2026,
            "Nueva causa",
        ),
        director="Dra. Mar\u00eda Del Carmen",
        fecha_sesion=date(2026, 12, 11),
    )

    result = asyncio.run(services.dictamen_controller.generate_pdf(request))
    saved_path = asyncio.run(
        services.document_store.save("selected.pdf", result.content)
    )

    assert result is document
    assert pdf_generator.calls == [request]
    assert services.document_store is document_store
    assert document_store.save_calls == [("selected.pdf", b"%PDF-test")]
    assert saved_path.name == "memory-output.pdf"


def test_production_services_wire_real_pdf_generation_and_local_storage():
    services = build_services(
        settings=api_settings(),
        transport=httpx.MockTransport(lambda request: httpx.Response(500)),
    )
    request = PdfRequest(
        dictamen=Dictamen(
            "CSE-0001-26",
            "2021320863",
            "Ana L\u00f3pez Mart\u00ednez",
            date(2026, 8, 30),
            2026,
            "Art\u00edculo 56",
        ),
        director="Dra. Mar\u00eda Del Carmen",
        fecha_sesion=date(2026, 12, 11),
    )

    document = asyncio.run(services.dictamen_controller.generate_pdf(request))

    assert isinstance(services.document_store, LocalPdfDocumentStore)
    assert isinstance(services.dictamen_controller._pdf_generator, RealPdfGenerator)
    assert document.filename == "2021320863_dictamen_2026-08-30.pdf"
    assert document.content.startswith(b"%PDF-")
    assert document.is_simulation is False


def test_production_services_establish_the_api_identity_and_shared_session():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/auth/me":
            return httpx.Response(200, json=AUTH_ME_RESPONSE)
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

    assert session is services.auth_session.current
    assert session.current_user is not None
    assert session.current_user.username == "identity-from-api"
    assert services.auth_session.access_token == "access-token"


def test_production_services_register_users_through_the_shared_api_client():
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/api/auth/login":
            return httpx.Response(
                200,
                json={
                    "access_token": "shared-access",
                    "refresh_token": "shared-refresh",
                },
            )
        if request.url.path == "/api/auth/me":
            return httpx.Response(200, json=AUTH_ME_RESPONSE)
        assert request.url.path == "/api/auth/register"
        assert request.headers["Authorization"] == "Bearer shared-access"
        return httpx.Response(
            201,
            json={
                **REGISTER_RESPONSE,
                "user": {**REGISTER_RESPONSE["user"], "is_admin": True},
            },
        )

    services = build_services(
        settings=api_settings(),
        transport=httpx.MockTransport(handler),
    )
    asyncio.run(services.auth_controller.login("directivo", "secreto"))

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
    assert [(request.method, request.url.path) for request in requests] == [
        ("POST", "/api/auth/login"),
        ("GET", "/api/auth/me"),
        ("POST", "/api/auth/register"),
    ]
    assert json.loads(requests[-1].content) == {
        "username": "nuevo",
        "password": "secreto",
        "is_admin": True,
    }


def test_normal_production_session_keeps_queries_and_blocks_every_mutation():
    requests = []
    normal_identity = {**AUTH_ME_RESPONSE, "username": "consulta", "is_admin": False}

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append((request.method, request.url.path))
        if request.url.path == "/api/auth/login":
            return httpx.Response(
                200,
                json={
                    "access_token": "shared-access",
                    "refresh_token": "shared-refresh",
                },
            )
        if request.url.path == "/api/auth/me":
            return httpx.Response(200, json=normal_identity)
        if request.url.path == "/api/inscritos/2022630000":
            return httpx.Response(200, json=INSCRITO_RESPONSE)
        if request.url.path == "/api/reprobados":
            return httpx.Response(200, json=paginated_response(REPROBADO_ITEM))
        if request.url.path == "/api/dictaminaciones" and request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "total": 1,
                    "skip": 0,
                    "limit": 100,
                    "items": [CREATED_RESPONSE],
                },
            )
        raise AssertionError("A normal user must not reach an API mutation.")

    services = build_services(
        settings=api_settings(),
        transport=httpx.MockTransport(handler),
    )
    session = asyncio.run(services.auth_controller.login("consulta", "secreto"))
    alumno = asyncio.run(services.alumno_controller.find_inscrito("2022630000"))
    failed_candidate = asyncio.run(
        services.dictamen_controller.find_student_candidate(
            "reprobado", "2022630000", "20262"
        )
    )
    page = asyncio.run(
        services.dictamen_controller.search_page(
            DictamenFilter(anio=2026),
            page=1,
        )
    )
    current = page.items[0]

    assert session.current_user is not None
    assert session.current_user.is_admin is False
    assert alumno.boleta == "2022630000"
    assert failed_candidate.total_reprobadas == 1
    assert page.total == 1

    with pytest.raises(AuthorizationError):
        asyncio.run(
            services.user_controller.register(
                "nuevo", "secreto", "secreto", False
            )
        )
    with pytest.raises(AuthorizationError):
        asyncio.run(
            services.dictamen_controller.create(
                alumno=alumno,
                dictaminacion="CONTENIDO CONFIDENCIAL DEL DICTAMEN",
                director="Dirección ESIQIE",
                materias=(),
                reference=date(2026, 8, 29),
                fecha_sesion=date(2026, 12, 11),
            )
        )
    with pytest.raises(AuthorizationError):
        asyncio.run(
            services.dictamen_controller.update_dictaminacion(
                current, "DICTAMEN ACTUALIZADO"
            )
        )
    with pytest.raises(AuthorizationError):
        asyncio.run(services.dictamen_controller.delete_dictamenes((current,)))

    assert requests == [
        ("POST", "/api/auth/login"),
        ("GET", "/api/auth/me"),
        ("GET", "/api/inscritos/2022630000"),
        ("GET", "/api/reprobados"),
        ("GET", "/api/dictaminaciones"),
    ]


def test_services_clear_the_whole_session_on_logout():
    services = build_test_services()

    services.clear_authentication()

    assert services.auth_session.current is None


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
        if request.url.path == "/api/auth/me":
            return httpx.Response(200, json=AUTH_ME_RESPONSE)
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
    assert paths == [
        "/api/auth/login",
        "/api/auth/me",
        "/api/inscritos/2022630000",
    ]


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
        if request.url.path == "/api/auth/me":
            return httpx.Response(200, json=AUTH_ME_RESPONSE)
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
    assert paths == ["/api/auth/login", "/api/auth/me", "/api/reprobados"]


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
        if request.url.path == "/api/auth/me":
            return httpx.Response(200, json=AUTH_ME_RESPONSE)
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
    assert [request.method for request in requests] == [
        "POST",
        "GET",
        "GET",
        "POST",
    ]


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
        if request.url.path == "/api/auth/me":
            return httpx.Response(200, json=AUTH_ME_RESPONSE)
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
    assert paths == ["/api/auth/login", "/api/auth/me", "/api/dictaminaciones"]


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
        if request.url.path == "/api/auth/me":
            return httpx.Response(200, json=AUTH_ME_RESPONSE)
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
    assert [request.method for request in requests] == ["POST", "GET", "PUT"]


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
        if request.url.path == "/api/auth/me":
            return httpx.Response(200, json=AUTH_ME_RESPONSE)
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
    assert [request.method for request in requests] == ["POST", "GET", "DELETE"]
