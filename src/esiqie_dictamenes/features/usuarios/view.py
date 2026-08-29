import flet as ft

from esiqie_dictamenes.core.context import use_app_context
from esiqie_dictamenes.core.errors import to_user_message
from esiqie_dictamenes.shared.components.feedback import feedback
from esiqie_dictamenes.shared.components.page_header import page_header


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


@ft.component
def CreateUserView() -> ft.Control:
    context = use_app_context()
    username, set_username = ft.use_state("")
    password, set_password = ft.use_state("")
    confirmation, set_confirmation = ft.use_state("")
    access, set_access = ft.use_state("standard")
    message, set_message = ft.use_state("")
    is_error, set_is_error = ft.use_state(False)

    async def submit() -> None:
        try:
            await _register_user(
                context.services,
                username,
                password,
                confirmation,
                access == "admin",
            )
            set_message("Usuario creado en modo demostración.")
            set_is_error(False)
        except Exception as error:
            set_message(to_user_message(error))
            set_is_error(True)

    return ft.Column(
        [
            page_header("Crear usuario", "Registra credenciales y asigna el nivel de acceso."),
            feedback(message, error=is_error),
            ft.TextField(label="Usuario", value=username, on_change=lambda e: set_username(e.control.value), key="user-username"),
            ft.TextField(label="Contraseña", value=password, password=True, can_reveal_password=True, on_change=lambda e: set_password(e.control.value), key="user-password"),
            ft.TextField(label="Confirmar contraseña", value=confirmation, password=True, can_reveal_password=True, on_change=lambda e: set_confirmation(e.control.value), key="user-password-confirmation"),
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
            ft.Row([ft.Button("Crear usuario", on_click=submit, key="user-submit")], alignment=ft.MainAxisAlignment.END),
        ],
        width=680,
        scroll=ft.ScrollMode.AUTO,
    )
