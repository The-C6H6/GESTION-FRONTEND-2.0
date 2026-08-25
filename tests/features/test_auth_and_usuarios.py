import asyncio

import pytest

from esiqie_dictamenes.core.errors import ValidationError
from esiqie_dictamenes.features.auth.controller import AuthController
from esiqie_dictamenes.features.usuarios.controller import UserController
from esiqie_dictamenes.infrastructure.demo.auth_repository import DemoAuthRepository


def test_demo_login_creates_an_admin_demo_session():
    controller = AuthController(DemoAuthRepository())

    session = asyncio.run(controller.login("directivo", "secreto"))

    assert session.username == "directivo"
    assert session.is_admin is True
    assert session.is_demo is True


def test_login_rejects_empty_credentials():
    controller = AuthController(DemoAuthRepository())

    with pytest.raises(ValidationError, match="Usuario y contraseña"):
        asyncio.run(controller.login("", ""))


def test_user_registration_rejects_different_passwords():
    controller = UserController(DemoAuthRepository())

    with pytest.raises(ValidationError, match="no coinciden"):
        asyncio.run(controller.register("nuevo", "secreto", "otro", False))


def test_user_registration_maps_administrator_access():
    repository = DemoAuthRepository()
    controller = UserController(repository)

    asyncio.run(controller.register("nuevo", "secreto", "secreto", True))

    assert repository.registered_users[0].username == "nuevo"
    assert repository.registered_users[0].is_admin is True
