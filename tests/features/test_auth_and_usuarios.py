import asyncio
from types import SimpleNamespace

import flet as ft
import pytest

from esiqie_dictamenes.core.errors import AuthorizationError, ValidationError
from esiqie_dictamenes.features.auth.controller import AuthController
from esiqie_dictamenes.features.usuarios.controller import UserController
from esiqie_dictamenes.features.usuarios import view as usuarios_view
from esiqie_dictamenes.shared.request_gate import RequestGate
from tests.helpers import (
    RecordingUserRepository,
    RejectingLoginRepository,
    authenticated_store,
    build_test_services,
)


def test_login_rejects_empty_credentials():
    controller = AuthController(RejectingLoginRepository())

    with pytest.raises(ValidationError, match="Usuario y contraseña"):
        asyncio.run(controller.login("", ""))


def test_user_registration_rejects_different_passwords():
    store = authenticated_store()
    controller = UserController(RecordingUserRepository(), store.require_admin)

    with pytest.raises(ValidationError, match="no coinciden"):
        asyncio.run(controller.register("nuevo", "secreto", "otro", False))


def test_user_registration_maps_administrator_access():
    repository = RecordingUserRepository()
    store = authenticated_store()
    controller = UserController(repository, store.require_admin)

    asyncio.run(controller.register("nuevo", "secreto", "secreto", True))

    assert repository.registered_users[0].username == "nuevo"
    assert repository.registered_users[0].is_admin is True


def test_user_registration_maps_standard_access_and_normalizes_username():
    repository = RecordingUserRepository()
    store = authenticated_store()
    controller = UserController(repository, store.require_admin)

    user = asyncio.run(
        controller.register("  consulta  ", "dummy123", "dummy123", False)
    )

    assert user.username == "consulta"
    assert user.is_admin is False
    assert repository.registered_users == [user]


@pytest.mark.parametrize(
    ("username", "password", "confirmation"),
    [
        ("   ", "dummy123", "dummy123"),
        ("nuevo", "", ""),
        ("nuevo", "dummy123", "different"),
    ],
)
def test_local_registration_validation_never_reaches_repository(
    username,
    password,
    confirmation,
):
    repository = RecordingUserRepository()
    store = authenticated_store()
    controller = UserController(repository, store.require_admin)

    with pytest.raises(ValidationError):
        asyncio.run(
            controller.register(
                username,
                password,
                confirmation,
                False,
            )
        )

    assert repository.registered_users == []


def test_normal_user_registration_is_rejected_before_repository_access():
    repository = RecordingUserRepository()
    store = authenticated_store(is_admin=False)
    controller = UserController(repository, store.require_admin)

    with pytest.raises(AuthorizationError):
        asyncio.run(controller.register("nuevo", "secreto", "secreto", False))

    assert repository.registered_users == []


def test_normal_user_registration_is_rejected_before_form_validation():
    repository = RecordingUserRepository()
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


@pytest.mark.parametrize(
    ("access", "expected"),
    [("standard", False), ("admin", True)],
)
def test_registration_access_maps_only_supported_selector_values(access, expected):
    assert usuarios_view._access_is_admin(access) is expected


def test_registration_access_rejects_an_unknown_selector_value():
    with pytest.raises(ValidationError, match="nivel de acceso"):
        usuarios_view._access_is_admin("unexpected")


def test_registration_submit_row_disables_action_and_shows_loading_indicator():
    row = usuarios_view._submit_row(True, lambda: None)
    button, progress = row.controls

    assert isinstance(button, ft.Button)
    assert button.key == "user-submit"
    assert button.disabled is True
    assert isinstance(progress, ft.ProgressRing)
    assert progress.visible is True


def test_registration_workflow_allows_only_one_concurrent_request():
    async def scenario():
        store = authenticated_store()
        started = asyncio.Event()
        release = asyncio.Event()
        calls = []
        loading_states = []

        class Controller:
            async def register(self, *args):
                calls.append(args)
                started.set()
                await release.wait()

        services = SimpleNamespace(
            auth_session=store,
            user_controller=Controller(),
        )
        gate = RequestGate()
        callbacks = {
            "set_loading": loading_states.append,
            "set_password": lambda value: None,
            "set_confirmation": lambda value: None,
            "set_message": lambda value: None,
            "set_is_error": lambda value: None,
        }

        first = asyncio.create_task(
            usuarios_view._submit_registration(
                gate=gate,
                services=services,
                username="nuevo",
                password="dummy123",
                confirmation="dummy123",
                access="standard",
                **callbacks,
            )
        )
        await started.wait()
        second_result = await usuarios_view._submit_registration(
            gate=gate,
            services=services,
            username="nuevo",
            password="dummy123",
            confirmation="dummy123",
            access="standard",
            **callbacks,
        )
        release.set()
        first_result = await first
        return calls, loading_states, first_result, second_result, gate.active

    calls, loading_states, first_result, second_result, active = asyncio.run(
        scenario()
    )

    assert calls == [("nuevo", "dummy123", "dummy123", False)]
    assert loading_states == [True, False]
    assert first_result is True
    assert second_result is False
    assert active is False


def test_successful_registration_clears_only_password_fields():
    store = authenticated_store()
    calls = []

    class Controller:
        async def register(self, *args):
            calls.append(args)

    services = SimpleNamespace(
        auth_session=store,
        user_controller=Controller(),
    )
    loading_states = []
    passwords = []
    confirmations = []
    messages = []
    error_states = []

    result = asyncio.run(
        usuarios_view._submit_registration(
            gate=RequestGate(),
            services=services,
            username="nuevo",
            password="dummy123",
            confirmation="dummy123",
            access="admin",
            set_loading=loading_states.append,
            set_password=passwords.append,
            set_confirmation=confirmations.append,
            set_message=messages.append,
            set_is_error=error_states.append,
        )
    )

    assert result is True
    assert calls == [("nuevo", "dummy123", "dummy123", True)]
    assert loading_states == [True, False]
    assert passwords == [""]
    assert confirmations == [""]
    assert messages == ["Usuario creado correctamente."]
    assert error_states == [False]


def test_failed_registration_restores_submit_and_preserves_form_values():
    store = authenticated_store()

    class Controller:
        async def register(self, *args):
            raise ValidationError("El nombre de usuario ya existe.")

    services = SimpleNamespace(
        auth_session=store,
        user_controller=Controller(),
    )
    loading_states = []
    passwords = []
    confirmations = []
    messages = []
    error_states = []

    result = asyncio.run(
        usuarios_view._submit_registration(
            gate=RequestGate(),
            services=services,
            username="existente",
            password="dummy123",
            confirmation="dummy123",
            access="standard",
            set_loading=loading_states.append,
            set_password=passwords.append,
            set_confirmation=confirmations.append,
            set_message=messages.append,
            set_is_error=error_states.append,
        )
    )

    assert result is False
    assert loading_states == [True, False]
    assert passwords == []
    assert confirmations == []
    assert messages == ["El nombre de usuario ya existe."]
    assert error_states == [True]


def test_invalid_access_never_reaches_registration_controller():
    store = authenticated_store()
    calls = []

    class Controller:
        async def register(self, *args):
            calls.append(args)

    services = SimpleNamespace(
        auth_session=store,
        user_controller=Controller(),
    )
    messages = []

    result = asyncio.run(
        usuarios_view._submit_registration(
            gate=RequestGate(),
            services=services,
            username="nuevo",
            password="dummy123",
            confirmation="dummy123",
            access="unexpected",
            set_loading=lambda value: None,
            set_password=lambda value: None,
            set_confirmation=lambda value: None,
            set_message=messages.append,
            set_is_error=lambda value: None,
        )
    )

    assert result is False
    assert calls == []
    assert messages == ["Selecciona un nivel de acceso v\u00e1lido."]
