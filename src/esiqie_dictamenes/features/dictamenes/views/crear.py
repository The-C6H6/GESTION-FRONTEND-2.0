from datetime import date

import flet as ft

from esiqie_dictamenes.core.context import use_app_context
from esiqie_dictamenes.core.errors import to_user_message
from esiqie_dictamenes.features.dictamenes.periodos import current_period
from esiqie_dictamenes.features.alumnos.views.reprobados import eligible_subjects_table
from esiqie_dictamenes.shared.components.feedback import feedback
from esiqie_dictamenes.shared.components.page_header import page_header


@ft.component
def DictamenCreateView() -> ft.Control:
    context = use_app_context()
    source, set_source = ft.use_state("inscrito")
    query, set_query = ft.use_state("")
    period, set_period = ft.use_state(current_period(date.today()))
    alumno, set_alumno = ft.use_state(None)
    materias, set_materias = ft.use_state(())
    director, set_director = ft.use_state("")
    dictaminacion, set_dictaminacion = ft.use_state("")
    message, set_message = ft.use_state("")
    is_error, set_is_error = ft.use_state(False)

    async def search() -> None:
        try:
            if source == "inscrito":
                set_alumno(await context.services.alumno_controller.find_inscrito(query))
                set_materias(())
            else:
                candidate = await context.services.dictamen_controller.find_reprobado_candidate(
                    query, period
                )
                set_alumno(candidate.alumno)
                set_materias(candidate.materias)
            set_message("")
            set_is_error(False)
        except Exception as error:
            set_alumno(None)
            set_materias(())
            set_message(to_user_message(error))
            set_is_error(True)

    async def create() -> None:
        try:
            if alumno is None:
                raise ValueError("Primero busca y selecciona un alumno.")
            result = await context.services.dictamen_controller.create(
                alumno=alumno,
                dictaminacion=dictaminacion,
                director=director,
                materias=materias,
                reference=date.today(),
            )
            set_message(
                f"Dictamen {result.dictamen.clave} creado. PDF {result.document.filename} simulado."
            )
            set_is_error(False)
        except ValueError as error:
            set_message(str(error))
            set_is_error(True)
        except Exception as error:
            set_message(to_user_message(error))
            set_is_error(True)

    student_card = ft.Container()
    if alumno:
        student_card = ft.Card(
            content=ft.Container(
                padding=16,
                content=ft.Column(
                    [
                        ft.Text(alumno.nombre, size=20, weight=ft.FontWeight.BOLD),
                        ft.Text(f"Boleta: {alumno.boleta}"),
                        ft.Text(f"Carrera: {alumno.carrera}"),
                        eligible_subjects_table(materias) if source == "reprobado" else ft.Container(),
                    ]
                ),
            )
        )
    return ft.Column(
        [
            page_header("Nuevo dictamen", "Busca un alumno inscrito o reprobado y genera su dictamen."),
            ft.Dropdown(
                label="Origen de la búsqueda",
                value=source,
                options=[
                    ft.DropdownOption(key="inscrito", text="Alumno inscrito"),
                    ft.DropdownOption(key="reprobado", text="Alumno reprobado"),
                ],
                on_select=lambda e: set_source(e.control.value),
                key="dictamen-source",
            ),
            ft.Row(
                [
                    ft.TextField(
                        label="Boleta o nombre del alumno",
                        value=query,
                        on_change=lambda e: set_query(e.control.value),
                        expand=True,
                        key="dictamen-student-query",
                    ),
                    ft.TextField(
                        label="Periodo actual",
                        value=period,
                        on_change=lambda e: set_period(e.control.value),
                        width=170,
                        visible=source == "reprobado",
                        key="dictamen-current-period",
                    ),
                    ft.Button("Buscar", on_click=search, key="dictamen-student-search"),
                ]
            ),
            feedback(message, error=is_error),
            student_card,
            ft.TextField(
                label="Nombre del director",
                value=director,
                on_change=lambda e: set_director(e.control.value),
                key="dictamen-director",
            ),
            ft.TextField(
                label="Dictaminación",
                value=dictaminacion,
                multiline=True,
                min_lines=4,
                on_change=lambda e: set_dictaminacion(e.control.value),
                key="dictamen-text",
            ),
            ft.Row(
                [ft.Button("Dictaminar y generar PDF", on_click=create, key="dictamen-create")],
                alignment=ft.MainAxisAlignment.END,
            ),
        ],
        scroll=ft.ScrollMode.AUTO,
        expand=True,
    )
