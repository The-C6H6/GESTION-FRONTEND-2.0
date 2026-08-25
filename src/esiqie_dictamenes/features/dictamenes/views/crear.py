from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import date, datetime

import flet as ft

from esiqie_dictamenes.core.context import use_app_context
from esiqie_dictamenes.core.errors import to_user_message
from esiqie_dictamenes.core.routes import RoutePath
from esiqie_dictamenes.features.dictamenes.pdf import format_session_date
from esiqie_dictamenes.features.dictamenes.periodos import current_period
from esiqie_dictamenes.features.alumnos.views.reprobados import eligible_subjects_table
from esiqie_dictamenes.shared.components.feedback import feedback
from esiqie_dictamenes.shared.components.page_header import page_header


class _RequestGate:
    def __init__(self) -> None:
        self.active = False

    def enter(self) -> bool:
        if self.active:
            return False
        self.active = True
        return True

    def leave(self) -> None:
        self.active = False


@dataclass(frozen=True)
class _StudentSearchResult:
    alumno: object
    materias: tuple
    total_reprobadas: int


async def _run_guarded_search(
    gate: _RequestGate,
    set_busy: Callable[[bool], None],
    operation: Callable[[], Awaitable[None]],
) -> bool:
    if not gate.enter():
        return False
    set_busy(True)
    try:
        await operation()
        return True
    finally:
        set_busy(False)
        gate.leave()


async def _find_student(services, source: str, query: str, period: str):
    alumno = await services.alumno_controller.find_inscrito(query)
    if source == "reprobado":
        return await services.dictamen_controller.find_reprobado_candidate_for_student(
            alumno,
            period,
        )
    return _StudentSearchResult(alumno, (), 0)


def _redirect_expired_session(context, error: Exception, navigate: Callable) -> bool:
    if not context.handle_session_error(error):
        return False
    navigate(RoutePath.LOGIN)
    return True


def _failed_subjects_empty_message(total_reprobadas: int) -> str:
    if total_reprobadas == 0:
        return "El alumno no tiene materias reprobadas registradas."
    return "No hay materias que cumplan la regla 19 ≤ diferencia < 29."


def _build_create_button(search_busy: bool, on_click: Callable) -> ft.Button:
    return ft.Button(
        "Dictaminar y generar PDF",
        on_click=on_click,
        disabled=search_busy,
        key="dictamen-create",
    )


def _as_date(value: date | datetime) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    raise ValueError("DatePicker must provide a date value.")


def _build_session_date_picker(
    value: date,
    on_change: Callable,
    on_dismiss: Callable,
) -> ft.DatePicker:
    return ft.DatePicker(
        value=value,
        current_date=date.today(),
        first_date=date(2000, 1, 1),
        last_date=date(2100, 12, 31),
        locale=ft.Locale("es", "MX"),
        entry_mode=ft.DatePickerEntryMode.CALENDAR_ONLY,
        help_text="Selecciona la fecha de sesión",
        cancel_text="Cancelar",
        confirm_text="Aceptar",
        on_change=on_change,
        on_dismiss=on_dismiss,
        key="dictamen-session-date-picker",
    )


@ft.component
def DictamenCreateView() -> ft.Control:
    context = use_app_context()
    search_gate = ft.use_memo(_RequestGate, [])
    source, set_source = ft.use_state("inscrito")
    query, set_query = ft.use_state("")
    period, set_period = ft.use_state(current_period(date.today()))
    alumno, set_alumno = ft.use_state(None)
    materias, set_materias = ft.use_state(())
    total_reprobadas, set_total_reprobadas = ft.use_state(0)
    director, set_director = ft.use_state("")
    dictaminacion, set_dictaminacion = ft.use_state("")
    fecha_sesion, set_fecha_sesion = ft.use_state(date.today())
    show_date_picker, set_show_date_picker = ft.use_state(False)
    message, set_message = ft.use_state("")
    is_error, set_is_error = ft.use_state(False)
    search_busy, set_search_busy = ft.use_state(False)

    def select_session_date(event: ft.Event[ft.DatePicker]) -> None:
        if event.control.value is not None:
            set_fecha_sesion(_as_date(event.control.value))
        set_show_date_picker(False)

    picker = _build_session_date_picker(
        fecha_sesion,
        on_change=select_session_date,
        on_dismiss=lambda _event: set_show_date_picker(False),
    )
    ft.use_dialog(picker if show_date_picker else None)

    async def search() -> None:
        async def operation() -> None:
            result = await _find_student(context.services, source, query, period)
            set_alumno(result.alumno)
            set_materias(result.materias)
            set_total_reprobadas(result.total_reprobadas)
            set_message("")
            set_is_error(False)

        try:
            await _run_guarded_search(search_gate, set_search_busy, operation)
        except Exception as error:
            set_alumno(None)
            set_materias(())
            set_total_reprobadas(0)
            set_message(to_user_message(error))
            set_is_error(True)
            _redirect_expired_session(
                context,
                error,
                ft.context.page.navigate,
            )

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
                fecha_sesion=fecha_sesion,
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
                        eligible_subjects_table(
                            materias,
                            empty_message=_failed_subjects_empty_message(
                                total_reprobadas
                            ),
                        )
                        if source == "reprobado"
                        else ft.Container(),
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
                disabled=search_busy,
                key="dictamen-source",
            ),
            ft.Row(
                [
                    ft.TextField(
                        label="Número de boleta",
                        value=query,
                        on_change=lambda e: set_query(e.control.value),
                        disabled=search_busy,
                        expand=True,
                        key="dictamen-student-query",
                    ),
                    ft.TextField(
                        label="Periodo actual",
                        value=period,
                        on_change=lambda e: set_period(e.control.value),
                        width=170,
                        visible=source == "reprobado",
                        disabled=search_busy,
                        key="dictamen-current-period",
                    ),
                    ft.Button(
                        "Buscando..." if search_busy else "Buscar",
                        on_click=search,
                        disabled=search_busy,
                        key="dictamen-student-search",
                    ),
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
            ft.Row(
                [
                    ft.TextField(
                        label="Fecha de sesión",
                        value=format_session_date(fecha_sesion),
                        read_only=True,
                        expand=True,
                        key="dictamen-session-date",
                    ),
                    ft.Button(
                        "Elegir fecha",
                        icon=ft.Icons.CALENDAR_MONTH,
                        on_click=lambda: set_show_date_picker(True),
                        key="dictamen-session-date-open",
                    ),
                ]
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
                [_build_create_button(search_busy, create)],
                alignment=ft.MainAxisAlignment.END,
            ),
        ],
        scroll=ft.ScrollMode.AUTO,
        expand=True,
    )
