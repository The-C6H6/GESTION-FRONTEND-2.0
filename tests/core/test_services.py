import asyncio

import httpx

from esiqie_dictamenes.core.services import build_demo_services, build_services
from esiqie_dictamenes.core.settings import ApiSettings
from tests.infrastructure.http.test_inscrito_repository import INSCRITO_RESPONSE


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
    def handler(request: httpx.Request) -> httpx.Response:
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
        ),
        transport=httpx.MockTransport(handler),
    )
    asyncio.run(services.auth_controller.login("directivo", "secreto"))

    alumno = asyncio.run(
        services.alumno_controller.find_inscrito(" 2022630000 ")
    )

    assert alumno.nombre == "María Hernández García"


def test_production_services_keep_reprobados_in_demo_mode():
    def reject_network(request: httpx.Request) -> httpx.Response:
        raise AssertionError("Reprobados must remain in demo mode.")

    services = build_services(
        settings=ApiSettings(
            "http://api.test",
            "/api/auth/login",
            "/api/inscritos/{boleta}",
            "/api/reprobados",
        ),
        transport=httpx.MockTransport(reject_network),
    )

    candidate = asyncio.run(
        services.dictamen_controller.find_reprobado_candidate(
            "2024320678",
            "20271",
        )
    )

    assert candidate.alumno.boleta == "2024320678"
    assert candidate.materias
