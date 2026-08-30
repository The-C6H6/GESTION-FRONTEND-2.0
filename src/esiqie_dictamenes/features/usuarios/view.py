from collections.abc import Awaitable, Callable

import flet as ft

from esiqie_dictamenes.core.context import use_app_context
from esiqie_dictamenes.core.errors import ValidationError, to_user_message
from esiqie_dictamenes.shared.components.feedback import feedback
from esiqie_dictamenes.shared.components.page_header import page_header
from esiqie_dictamenes.shared.request_gate import RequestGate


async def _register_user(
    services,
    username: str,
    password: str,
    confirmation: str,
    is_admin: bool,
) -> None:
    services.auth_session.require_admin()
    await services.user_controller.register(
        username,
        password,
        confirmation,
        is_admin,
    )


def _access_is_admin(access: str) -> bool:
    if access == "standard":
        return False
    if access == "admin":
        return True
    raise ValidationError("Selecciona un nivel de acceso válido.")


async def _submit_registration(
    *,
    gate: RequestGate,
    services,
    username: str,
    password: str,
    confirmation: str,
    access: str,
    set_loading: Callable[[bool], None],
    set_password: Callable[[str], None],
    set_confirmation: Callable[[str], None],
    set_message: Callable[[str], None],
    set_is_error: Callable[[bool], None],
) -> bool:
    if not gate.enter():
        return False
    set_loading(True)
    try:
        await _register_user(
            services,
            username,
            password,
            confirmation,
            _access_is_admin(access),
        )
        set_password("")
        set_confirmation("")
        set_message("Usuario creado correctamente.")
        set_is_error(False)
        return True
    except Exception as error:
        set_message(to_user_message(error))
        set_is_error(True)
        return False
    finally:
        set_loading(False)
        gate.leave()


def _submit_row(
    loading: bool,
    on_submit: Callable[[], Awaitable[None]],
) -> ft.Row:
    return ft.Row(
        [
            ft.Button(
                "Crear usuario",
                on_click=on_submit,
                disabled=loading,
                key="user-submit",
            ),
            ft.ProgressRing(
                width=20,
                height=20,
                visible=loading,
                key="user-submit-loading",
            ),
        ],
        alignment=ft.MainAxisAlignment.END,
    )


@ft.component
def CreateUserView() -> ft.Control:
    context = use_app_context()
    gate = ft.use_memo(RequestGate, [])
    username, set_username = ft.use_state("")
    password, set_password = ft.use_state("")
    confirmation, set_confirmation = ft.use_state("")
    access, set_access = ft.use_state("standard")
    message, set_message = ft.use_state("")
    is_error, set_is_error = ft.use_state(False)
    loading, set_loading = ft.use_state(False)

    async def submit() -> None:
        await _submit_registration(
            gate=gate,
            services=context.services,
            username=username,
            password=password,
            confirmation=confirmation,
            access=access,
            set_loading=set_loading,
            set_password=set_password,
            set_confirmation=set_confirmation,
            set_message=set_message,
            set_is_error=set_is_error,
        )

    return ft.Column(
        [
            page_header(
                "Crear usuario",
                "Registra credenciales y asigna el nivel de acceso.",
            ),
            feedback(message, error=is_error),
            ft.TextField(
                label="Usuario",
                value=username,
                on_change=lambda e: set_username(e.control.value),
                key="user-username",
            ),
            ft.TextField(
                label="Contraseña",
                value=password,
                password=True,
                can_reveal_password=True,
                on_change=lambda e: set_password(e.control.value),
                key="user-password",
            ),
            ft.TextField(
                label="Confirmar contraseña",
                value=confirmation,
                password=True,
                can_reveal_password=True,
                on_change=lambda e: set_confirmation(e.control.value),
                key="user-password-confirmation",
            ),
            ft.Dropdown(
                label="Nivel de acceso",
                value=access,
                options=[
                    ft.DropdownOption(key="standard", text="Usuario estándar"),
                    ft.DropdownOption(key="admin", text="Administrador"),
                ],
                on_select=lambda e: set_access(e.control.value),
                key="user-access",
            ),
            _submit_row(loading, submit),
        ],
        width=680,
        scroll=ft.ScrollMode.AUTO,
    )
