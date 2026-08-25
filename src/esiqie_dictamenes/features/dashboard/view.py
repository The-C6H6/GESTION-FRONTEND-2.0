import flet as ft

from esiqie_dictamenes.core.routes import RoutePath
from esiqie_dictamenes.shared.components.page_header import page_header


@ft.component
def DashboardView() -> ft.Control:
    cards = [
        ("Buscar dictámenes", "Consulta por boleta o año.", RoutePath.DICTAMENES),
        ("Nuevo dictamen", "Dictamina alumnos inscritos o reprobados.", RoutePath.NUEVO_DICTAMEN),
        ("Buscar inscrito", "Consulta la información académica del alumno.", RoutePath.INSCRITOS),
    ]
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
