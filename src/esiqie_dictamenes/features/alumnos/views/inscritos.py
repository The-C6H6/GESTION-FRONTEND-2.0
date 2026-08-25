import flet as ft

from esiqie_dictamenes.core.context import use_app_context
from esiqie_dictamenes.core.errors import to_user_message
from esiqie_dictamenes.core.routes import RoutePath
from esiqie_dictamenes.shared.components.feedback import feedback
from esiqie_dictamenes.shared.components.page_header import page_header


@ft.component
def InscritoSearchView() -> ft.Control:
    context = use_app_context()
    query, set_query = ft.use_state("")
    alumno, set_alumno = ft.use_state(None)
    message, set_message = ft.use_state("")

    async def search() -> None:
        try:
            set_alumno(await context.services.alumno_controller.find_inscrito(query))
            set_message("")
        except Exception as error:
            set_alumno(None)
            set_message(to_user_message(error))

    details = ft.Container()
    if alumno:
        details = ft.Card(
            content=ft.Container(
                padding=20,
                content=ft.Column(
                    [
                        ft.Text(alumno.nombre, size=22, weight=ft.FontWeight.BOLD),
                        ft.Text(f"Boleta: {alumno.boleta}"),
                        ft.Text(f"Carrera: {alumno.carrera}"),
                        ft.ResponsiveRow(
                            [
                                ft.Text(f"Edad: {alumno.edad}", col=6),
                                ft.Text(f"Género: {alumno.genero}", col=6),
                                ft.Text(f"Promedio: {alumno.promedio}", col=6),
                                ft.Text(f"Créditos inscritos: {alumno.creditos_inscritos}", col=6),
                                ft.Text(f"Periodo en que reprobó: {alumno.periodo_en_que_reprobo}", col=6),
                                ft.Text(f"Reprobadas: {alumno.reprobadas}", col=6),
                            ]
                        ),
                        ft.Button("Crear dictamen", on_click=lambda: ft.context.page.navigate(RoutePath.NUEVO_DICTAMEN)),
                    ]
                ),
            )
        )
    return ft.Column(
        [
            page_header("Buscar alumno inscrito", "Consulta la información académica por boleta."),
            ft.Row(
                [
                    ft.TextField(label="Número de boleta", value=query, on_change=lambda e: set_query(e.control.value), expand=True, key="inscrito-query"),
                    ft.Button("Buscar", on_click=search, key="inscrito-search"),
                ]
            ),
            feedback(message, error=True),
            details,
        ],
        scroll=ft.ScrollMode.AUTO,
        expand=True,
    )
