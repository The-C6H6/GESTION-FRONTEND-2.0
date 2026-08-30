import flet as ft

from esiqie_dictamenes.core.context import use_app_context
from esiqie_dictamenes.core.routes import RoutePath
from esiqie_dictamenes.core.theme import ESIQIE_BLUE, ESIQIE_BLUE_DARK, SURFACE
from esiqie_dictamenes.features.auth.models import AuthenticatedUser, Session


def session_status_label(session: Session | None) -> str:
    return "Acceso API · PDF en demostración"


def _navigation_items(
    user: AuthenticatedUser,
) -> tuple[tuple[str, RoutePath], ...]:
    if not user.is_admin:
        return (
            ("Inicio", RoutePath.DASHBOARD),
            ("Buscar dictámenes", RoutePath.DICTAMENES),
            ("Consultar alumnos", RoutePath.NUEVO_DICTAMEN),
            ("Buscar inscrito", RoutePath.INSCRITOS),
        )
    return (
        ("Inicio", RoutePath.DASHBOARD),
        ("Buscar dictámenes", RoutePath.DICTAMENES),
        ("Dictaminar", RoutePath.NUEVO_DICTAMEN),
        ("Eliminar dictámenes", RoutePath.ELIMINAR_DICTAMENES),
        ("Buscar inscrito", RoutePath.INSCRITOS),
        ("Crear usuario", RoutePath.NUEVO_USUARIO),
    )


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
    session = context.session
    assert session is not None
    current_user = session.current_user
    assert current_user is not None

    def logout() -> None:
        context.invalidate_session()
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
                *[
                    _nav_button(label, path)
                    for label, path in _navigation_items(current_user)
                ],
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
    header = ft.Container(
        bgcolor="#FFFFFF",
        padding=ft.Padding.symmetric(horizontal=24, vertical=14),
        content=ft.Row(
            [
                ft.Text("Sistema de Gestión de Dictámenes", weight=ft.FontWeight.BOLD, color=ESIQIE_BLUE),
                ft.Container(expand=True),
                ft.Text(
                    session_status_label(session),
                    color="#6C1538",
                    weight=ft.FontWeight.BOLD,
                ),
                ft.Text(current_user.username),
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
