from types import SimpleNamespace

import pytest

from esiqie_dictamenes.app import _private_route_redirect
from esiqie_dictamenes.core.context import AppContextValue
from esiqie_dictamenes.core.errors import (
    SessionChangedError,
    SessionExpiredError,
    ValidationError,
)
from esiqie_dictamenes.core.routes import (
    RoutePath,
    is_admin_route,
    is_protected_route,
)
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


@pytest.mark.parametrize(
    "route",
    [RoutePath.NUEVO_USUARIO, RoutePath.ELIMINAR_DICTAMENES],
)
def test_administrative_routes_redirect_normal_users_without_rendering(route):
    session = authenticated_store(is_admin=False).current
    assert session is not None

    assert is_admin_route(route) is True
    assert _private_route_redirect(route, session) == RoutePath.DASHBOARD


def test_read_only_ruling_candidate_route_remains_available_to_normal_users():
    session = authenticated_store(is_admin=False).current
    assert session is not None

    assert _private_route_redirect(RoutePath.NUEVO_DICTAMEN, session) is None


def test_unauthenticated_private_route_redirects_to_login():
    assert _private_route_redirect(RoutePath.DICTAMENES, None) == RoutePath.LOGIN


@pytest.mark.parametrize(
    "route",
    [
        RoutePath.DASHBOARD,
        RoutePath.DICTAMENES,
        RoutePath.NUEVO_DICTAMEN,
        RoutePath.ELIMINAR_DICTAMENES,
        RoutePath.INSCRITOS,
        RoutePath.NUEVO_USUARIO,
    ],
)
def test_administrators_can_open_every_private_route(route):
    session = authenticated_store(is_admin=True).current
    assert session is not None

    assert _private_route_redirect(route, session) is None


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
