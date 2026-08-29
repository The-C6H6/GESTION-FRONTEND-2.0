import asyncio
from types import SimpleNamespace

import pytest

from esiqie_dictamenes.core.errors import AuthorizationError, ValidationError
from esiqie_dictamenes.features.auth.controller import AuthController
from esiqie_dictamenes.features.usuarios.controller import UserController
from esiqie_dictamenes.infrastructure.demo.user_repository import DemoUserRepository
from esiqie_dictamenes.features.usuarios import view as usuarios_view
from tests.helpers import RejectingLoginRepository, authenticated_store, build_test_services


def test_login_rejects_empty_credentials():
    controller = AuthController(RejectingLoginRepository())

    with pytest.raises(ValidationError, match="Usuario y contraseña"):
        asyncio.run(controller.login("", ""))


def test_user_registration_rejects_different_passwords():
    store = authenticated_store()
    controller = UserController(DemoUserRepository(), store.require_admin)

    with pytest.raises(ValidationError, match="no coinciden"):
        asyncio.run(controller.register("nuevo", "secreto", "otro", False))


def test_user_registration_maps_administrator_access():
    repository = DemoUserRepository()
    store = authenticated_store()
    controller = UserController(repository, store.require_admin)

    asyncio.run(controller.register("nuevo", "secreto", "secreto", True))

    assert repository.registered_users[0].username == "nuevo"
    assert repository.registered_users[0].is_admin is True


def test_normal_user_registration_is_rejected_before_repository_access():
    repository = DemoUserRepository()
    store = authenticated_store(is_admin=False)
    controller = UserController(repository, store.require_admin)

    with pytest.raises(AuthorizationError):
        asyncio.run(controller.register("nuevo", "secreto", "secreto", False))

    assert repository.registered_users == []


def test_normal_user_registration_is_rejected_before_form_validation():
    repository = DemoUserRepository()
    store = authenticated_store(is_admin=False)
    controller = UserController(repository, store.require_admin)

    with pytest.raises(AuthorizationError):
        asyncio.run(controller.register("", "", "distinta", False))

    assert repository.registered_users == []


def test_hidden_registration_delegator_rejects_before_controller_call():
    auth_session = build_test_services(is_admin=False).auth_session
    calls = []

    class Controller:
        async def register(self, *args):
            calls.append(args)

    services = SimpleNamespace(
        auth_session=auth_session,
        user_controller=Controller(),
    )

    with pytest.raises(AuthorizationError):
        asyncio.run(
            usuarios_view._register_user(
                services,
                "nuevo",
                "secreto",
                "secreto",
                False,
            )
        )

    assert calls == []
