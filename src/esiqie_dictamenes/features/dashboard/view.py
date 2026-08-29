import flet as ft

from esiqie_dictamenes.core.context import use_app_context
from esiqie_dictamenes.core.routes import RoutePath
from esiqie_dictamenes.features.auth.models import AuthenticatedUser
from esiqie_dictamenes.shared.components.page_header import page_header


def _dashboard_cards(
    user: AuthenticatedUser,
) -> tuple[tuple[str, str, RoutePath], ...]:
    query_cards = (
        (
            "Buscar dictámenes",
            "Consulta por boleta o año.",
            RoutePath.DICTAMENES,
        ),
        (
            "Nuevo dictamen" if user.is_admin else "Consultar alumnos",
            (
                "Dictamina alumnos inscritos o reprobados."
                if user.is_admin
                else "Consulta alumnos inscritos o con materias reprobadas."
            ),
            RoutePath.NUEVO_DICTAMEN,
        ),
    )
    enrolled_card = (
        (
            "Buscar inscrito",
            "Consulta la información académica del alumno.",
            RoutePath.INSCRITOS,
        ),
    )
    if not user.is_admin:
        return query_cards + enrolled_card
    return query_cards + (
        (
            "Eliminar dictámenes",
            "Elimina uno o varios dictámenes.",
            RoutePath.ELIMINAR_DICTAMENES,
        ),
    ) + enrolled_card + (
        (
            "Crear usuario",
            "Registra un usuario del sistema.",
            RoutePath.NUEVO_USUARIO,
        ),
    )


@ft.component
def DashboardView() -> ft.Control:
    context = use_app_context()
    session = context.session
    assert session is not None
    current_user = session.current_user
    assert current_user is not None
    cards = _dashboard_cards(current_user)
    return ft.Column(
        [
            page_header("Inicio", "Accesos principales del sistema."),
            ft.ResponsiveRow(
                [
                    ft.Card(
                        content=ft.Container(
                            content=ft.Column(
                                [
                                    ft.Text(title, size=20, weight=ft.FontWeight.BOLD),
                                    ft.Text(description),
                                    ft.Button("Abrir", on_click=lambda _e, target=path: ft.context.page.navigate(target)),
                                ]
                            ),
                            padding=20,
                        ),
                        col={"sm": 12, "md": 6, "lg": 4},
                    )
                    for title, description, path in cards
                ]
            ),
        ],
        scroll=ft.ScrollMode.AUTO,
        expand=True,
    )
