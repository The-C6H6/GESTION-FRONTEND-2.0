import flet as ft

from esiqie_dictamenes.core.context import use_app_context
from esiqie_dictamenes.core.routes import RoutePath
from esiqie_dictamenes.core.theme import ESIQIE_BLUE, ESIQIE_BLUE_DARK, SURFACE


def _nav_button(label: str, path: str) -> ft.Control:
    active = ft.is_route_active(path)
    return ft.Container(
        content=ft.Text(
            label,
            color="#FFFFFF",
            weight=ft.FontWeight.BOLD if active else ft.FontWeight.NORMAL,
        ),
        bgcolor="#24FFFFFF" if active else None,
        border_radius=8,
        padding=ft.Padding.symmetric(horizontal=16, vertical=12),
        on_click=lambda: ft.context.page.navigate(path),
        key=f"nav-{path}",
    )


@ft.component
def AppShell(content: ft.Control) -> ft.Control:
    context = use_app_context()

    def logout() -> None:
        context.set_session(None)
        ft.context.page.navigate(RoutePath.LOGIN)

    sidebar = ft.Container(
        width=230,
        bgcolor=ESIQIE_BLUE_DARK,
        padding=18,
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Image(src="logo_esiqie.png", width=52, height=52),
                        ft.Text("ESIQIE\nDICTÁMENES", color="#FFFFFF", weight=ft.FontWeight.BOLD),
                    ]
                ),
                ft.Divider(color="#30FFFFFF", height=28),
                _nav_button("Inicio", RoutePath.DASHBOARD),
                _nav_button("Buscar dictámenes", RoutePath.DICTAMENES),
                _nav_button("Dictaminar", RoutePath.NUEVO_DICTAMEN),
                _nav_button("Eliminar dictámenes", RoutePath.ELIMINAR_DICTAMENES),
                _nav_button("Buscar inscrito", RoutePath.INSCRITOS),
                _nav_button("Crear usuario", RoutePath.NUEVO_USUARIO),
                ft.Container(expand=True),
                ft.Button(
                    "Cerrar sesión",
                    on_click=logout,
                    bgcolor="#FFFFFF",
                    color=ESIQIE_BLUE_DARK,
                    key="logout-button",
                ),
            ],
            expand=True,
            spacing=8,
        ),
    )
    username = context.session.username if context.session else ""
    header = ft.Container(
        bgcolor="#FFFFFF",
        padding=ft.Padding.symmetric(horizontal=24, vertical=14),
        content=ft.Row(
            [
                ft.Text("Sistema de Gestión de Dictámenes", weight=ft.FontWeight.BOLD, color=ESIQIE_BLUE),
                ft.Container(expand=True),
                ft.Text("Modo demostración", color="#6C1538", weight=ft.FontWeight.BOLD),
                ft.Text(username),
                ft.Image(src="ipn_logo.jpg", width=42, height=42),
            ]
        ),
    )
    return ft.Row(
        [
            sidebar,
            ft.Column(
                [
                    header,
                    ft.Container(content=content, padding=28, expand=True),
                ],
                expand=True,
                spacing=0,
            ),
        ],
        expand=True,
        spacing=0,
        vertical_alignment=ft.CrossAxisAlignment.STRETCH,
    )
