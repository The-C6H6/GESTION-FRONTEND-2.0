from types import SimpleNamespace

from esiqie_dictamenes.core.context import AppContextValue
from esiqie_dictamenes.core.errors import (
    SessionChangedError,
    SessionExpiredError,
    ValidationError,
)
from esiqie_dictamenes.core.routes import RoutePath, is_protected_route
from tests.helpers import authenticated_store


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


def test_app_context_invalidates_an_expired_api_session():
    store = authenticated_store()
    session_updates = []
    context = AppContextValue(
        services=SimpleNamespace(clear_authentication=store.clear),
        session=store.current,
        set_session=session_updates.append,
    )

    handled = context.handle_session_error(SessionExpiredError())

    assert handled is True
    assert store.current is None
    assert session_updates == [None]


def test_app_context_ignores_errors_unrelated_to_the_session():
    store = authenticated_store()
    session_updates = []
    context = AppContextValue(
        services=SimpleNamespace(clear_authentication=store.clear),
        session=store.current,
        set_session=session_updates.append,
    )

    handled = context.handle_session_error(ValidationError("Dato inválido."))

    assert handled is False
    assert session_updates == []


def test_app_context_does_not_invalidate_a_replacement_session():
    store = authenticated_store()
    replacement = store.current
    session_updates = []
    context = AppContextValue(
        services=SimpleNamespace(clear_authentication=store.clear),
        session=replacement,
        set_session=session_updates.append,
    )

    handled = context.handle_session_error(SessionChangedError())

    assert handled is False
    assert store.current is replacement
    assert session_updates == []
