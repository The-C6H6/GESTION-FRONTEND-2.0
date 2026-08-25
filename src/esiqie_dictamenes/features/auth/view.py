import flet as ft

from esiqie_dictamenes.core.context import use_app_context
from esiqie_dictamenes.core.errors import to_user_message
from esiqie_dictamenes.core.routes import RoutePath
from esiqie_dictamenes.core.theme import ESIQIE_BLUE, ESIQIE_BLUE_DARK
from esiqie_dictamenes.shared.components.feedback import feedback


@ft.component
def LoginView() -> ft.Control:
    context = use_app_context()
    username, set_username = ft.use_state("")
    password, set_password = ft.use_state("")
    message, set_message = ft.use_state("")
    busy, set_busy = ft.use_state(False)

    async def submit() -> None:
        set_busy(True)
        set_message("")
        try:
            session = await context.services.auth_controller.login(username, password)
            context.set_session(session)
            await ft.context.page.push_route(RoutePath.DASHBOARD)
        except Exception as error:
            set_message(to_user_message(error))
        finally:
            set_busy(False)

    return ft.Container(
        expand=True,
        bgcolor="#F5F7FB",
        content=ft.Row(
            [
                ft.Container(
                    expand=True,
                    bgcolor=ESIQIE_BLUE_DARK,
                    image=ft.DecorationImage(src="imagen_fondo.png", fit=ft.BoxFit.COVER, opacity=0.18),
                    content=ft.Column(
                        [
                            ft.Image(src="logo_esiqie.png", width=130),
                            ft.Text("ESIQIE-DICTÁMENES", size=32, color="#FFFFFF", weight=ft.FontWeight.BOLD),
                            ft.Text("Gestión académica institucional", size=18, color="#FFFFFF"),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                ),
                ft.Container(
                    width=460,
                    padding=48,
                    content=ft.Column(
                        [
                            ft.Text("Iniciar sesión", size=30, weight=ft.FontWeight.BOLD, color=ESIQIE_BLUE),
                            ft.Text("Usa cualquier usuario y contraseña en modo demostración."),
                            feedback(message, error=True),
                            ft.TextField(
                                label="Usuario",
                                value=username,
                                on_change=lambda event: set_username(event.control.value),
                                key="login-username",
                            ),
                            ft.TextField(
                                label="Contraseña",
                                value=password,
                                password=True,
                                can_reveal_password=True,
                                on_change=lambda event: set_password(event.control.value),
                                on_submit=submit,
                                key="login-password",
                            ),
                            ft.Button(
                                "Ingresar",
                                on_click=submit,
                                disabled=busy,
                                bgcolor=ESIQIE_BLUE,
                                color="#FFFFFF",
                                height=46,
                                key="login-submit",
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=18,
                    ),
                ),
            ],
            expand=True,
            spacing=0,
        ),
    )
