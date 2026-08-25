from esiqie_dictamenes.core.context import AppContextValue
from esiqie_dictamenes.core.errors import SessionExpiredError, ValidationError
from esiqie_dictamenes.core.routes import RoutePath, is_protected_route
from esiqie_dictamenes.core.services import build_demo_services
from esiqie_dictamenes.core.session import SessionState
from esiqie_dictamenes.features.auth.models import Session


def test_private_application_routes_are_protected():
    private_routes = (
        RoutePath.DASHBOARD,
        RoutePath.DICTAMENES,
        RoutePath.NUEVO_DICTAMEN,
        RoutePath.ELIMINAR_DICTAMENES,
        RoutePath.INSCRITOS,
        RoutePath.NUEVO_USUARIO,
    )

    assert all(is_protected_route(route) for route in private_routes)
    assert is_protected_route(RoutePath.LOGIN) is False


def test_session_state_can_start_and_close_a_session():
    state = SessionState()
    session = Session("directivo", is_admin=True, is_demo=True)

    state.start(session)
    assert state.current == session
    assert state.is_authenticated is True

    state.clear()
    assert state.current is None
    assert state.is_authenticated is False


def test_app_context_invalidates_an_expired_api_session():
    services = build_demo_services()
    services.auth_tokens.replace("expired-access", "expired-refresh")
    session_updates = []
    context = AppContextValue(
        services=services,
        session=Session("directivo", is_admin=False, is_demo=False),
        set_session=session_updates.append,
    )

    handled = context.handle_session_error(SessionExpiredError())

    assert handled is True
    assert services.auth_tokens.access_token is None
    assert session_updates == [None]


def test_app_context_ignores_errors_unrelated_to_the_session():
    services = build_demo_services()
    session_updates = []
    context = AppContextValue(
        services=services,
        session=Session("directivo", is_admin=False, is_demo=False),
        set_session=session_updates.append,
    )

    handled = context.handle_session_error(ValidationError("Dato inválido."))

    assert handled is False
    assert session_updates == []
