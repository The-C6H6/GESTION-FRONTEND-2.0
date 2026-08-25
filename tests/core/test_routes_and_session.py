from esiqie_dictamenes.core.routes import RoutePath, is_protected_route
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
