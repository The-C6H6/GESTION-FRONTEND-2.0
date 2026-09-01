from collections.abc import Awaitable, Callable
from datetime import date, datetime
from inspect import isawaitable

import flet as ft

from esiqie_dictamenes.core.context import use_app_context
from esiqie_dictamenes.core.errors import (
    ApiConnectionError,
    ApiTimeoutError,
    to_user_message,
)
from esiqie_dictamenes.core.routes import RoutePath
from esiqie_dictamenes.features.auth.models import AuthenticatedUser
from esiqie_dictamenes.features.dictamenes.models import Dictamen
from esiqie_dictamenes.features.dictamenes.pdf import format_session_date
from esiqie_dictamenes.features.dictamenes.periodos import current_period
from esiqie_dictamenes.features.alumnos.views.reprobados import eligible_subjects_table
from esiqie_dictamenes.features.dictamenes.views.pdf_output import (
    CreatePdfResult,
    FletPdfDestinationSelector,
    post_mutation_pdf_failure_message,
    require_desktop_pdf_output,
    saved_pdf_message,
    selector_result,
    use_file_picker,
)
from esiqie_dictamenes.shared.components.feedback import feedback
from esiqie_dictamenes.shared.components.page_header import page_header
from esiqie_dictamenes.shared.request_gate import RequestGate as _RequestGate


def _page_copy(user: AuthenticatedUser) -> tuple[str, str]:
    if user.is_admin:
        return (
            "Nuevo dictamen",
            "Selecciona el tipo de alumno y captura los datos de la sesión.",
        )
    return (
        "Consultar alumnos",
        "Consulta alumnos inscritos o con materias reprobadas.",
    )


def _admin_controls(
    user: AuthenticatedUser,
    controls: tuple[ft.Control, ...],
) -> tuple[ft.Control, ...]:
    return controls if user.is_admin else ()


async def _run_guarded_request(
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
    return await services.dictamen_controller.find_student_candidate(
        source,
        query,
        period,
    )


async def _create_dictamen(services, **kwargs):
    services.auth_session.require_admin()
    return await services.dictamen_controller.create(**kwargs)


def _redirect_expired_session(context, error: Exception, navigate: Callable) -> bool:
    if not context.handle_session_error(error):
        return False
    navigate(RoutePath.LOGIN)
    return True


def _creation_error_message(error: Exception) -> str:
    if isinstance(error, (ApiTimeoutError, ApiConnectionError)):
        return (
            "No se pudo confirmar si el dictamen fue creado. "
            "Verifica antes de intentarlo nuevamente."
        )
    return to_user_message(error)


def _creation_success_message(clave: str) -> str:
    return f"Dictamen creado correctamente. Clave: {clave}"


async def _create_pdf_workflow(
    *,
    page,
    selector,
    services,
    alumno,
    dictaminacion: str,
    director: str,
    materias: tuple,
    ruling_unavailable: bool = False,
    reference: date,
    fecha_sesion: date,
    on_post_mutation_failure: Callable[[Dictamen], None] | None = None,
) -> CreatePdfResult:
    """Run CREATE's destination, mutation, generation, and save stages."""
    services.auth_session.require_admin()
    if alumno is None:
        raise ValueError("Primero busca y selecciona un alumno.")
    if ruling_unavailable:
        raise ValueError(
            "El alumno no puede dictaminarse por que no tiene materias "
            "que se puedan dictaminar"
        )
    if not isinstance(dictaminacion, str) or not dictaminacion.strip():
        raise ValueError("La dictaminación es obligatoria.")
    if not isinstance(director, str) or not director.strip():
        raise ValueError("El director es obligatorio.")
    if not isinstance(fecha_sesion, date):
        raise ValueError("Selecciona la fecha de sesión en el calendario.")
    if not isinstance(reference, date):
        raise ValueError("La fecha del dictamen no es válida.")

    require_desktop_pdf_output(page)
    suggested = Dictamen(
        clave="",
        boleta=alumno.boleta,
        alumno=alumno.nombre,
        fecha=reference,
        anio=reference.year,
        dictaminacion=dictaminacion.strip(),
    )
    selected = selector_result(selector, suggested)
    if isawaitable(selected):
        selected = await selected
    if not selected:
        return CreatePdfResult(dictamen=None, cancelled=True)

    destination = services.document_store.validate_destination(selected)
    created = await _create_dictamen(
        services,
        alumno=alumno,
        dictaminacion=dictaminacion,
        director=director,
        materias=materias,
        reference=reference,
        fecha_sesion=fecha_sesion,
    )

    # The API mutation is intentionally not retried after this point. The
    # final key remains available to the user even if local output fails.
    try:
        document = await services.dictamen_controller.generate_pdf(
            created.pdf_request
        )
        saved_path = await services.document_store.save(
            destination,
            document.content,
        )
    except Exception:
        if on_post_mutation_failure is not None:
            on_post_mutation_failure(created.dictamen)
        return CreatePdfResult(
            dictamen=created.dictamen,
            cancelled=False,
            pdf_saved=False,
            message=post_mutation_pdf_failure_message(created.dictamen.clave),
        )

    return CreatePdfResult(
        dictamen=created.dictamen,
        saved_path=saved_path,
        pdf_saved=True,
        message=saved_pdf_message(created.dictamen.clave, saved_path),
    )


def _build_failed_subjects_section(
    materias: tuple,
    total_reprobadas: int,
) -> ft.Control:
    if materias:
        return eligible_subjects_table(materias)
    if total_reprobadas > 0:
        return ft.Column(
            [
                ft.Text(f"Materias reprobadas: {total_reprobadas}"),
                ft.Text(
                    "El alumno no puede dictaminarse por que no tiene materias "
                    "que se puedan dictaminar"
                ),
            ]
        )
    return ft.Container()


def _is_ruling_unavailable(
    source: str,
    alumno: object | None,
    materias: tuple,
    total_reprobadas: int,
) -> bool:
    return (
        source == "reprobado"
        and alumno is not None
        and not materias
        and total_reprobadas > 0
    )


def _change_search_criterion(
    value: str,
    set_criterion: Callable[[str], None],
    set_alumno: Callable[[object | None], None],
    set_materias: Callable[[tuple], None],
    set_total_reprobadas: Callable[[int], None],
) -> None:
    set_criterion(value)
    set_alumno(None)
    set_materias(())
    set_total_reprobadas(0)


def _build_create_button(
    search_busy: bool,
    create_busy: bool,
    on_click: Callable,
    *,
    ruling_unavailable: bool = False,
) -> ft.Button:
    return ft.Button(
        "Crear dictamen",
        on_click=on_click,
        disabled=search_busy or create_busy or ruling_unavailable,
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
    user = context.session.current_user
    assert user is not None
    search_gate = ft.use_memo(_RequestGate, [])
    create_gate = ft.use_memo(_RequestGate, [])
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
    create_busy, set_create_busy = ft.use_state(False)
    pdf_picker = use_file_picker()

    def select_session_date(event: ft.Event[ft.DatePicker]) -> None:
        if event.control.value is not None:
            set_fecha_sesion(_as_date(event.control.value))
        set_show_date_picker(False)

    picker = _build_session_date_picker(
        fecha_sesion,
        on_change=select_session_date,
        on_dismiss=lambda _event: set_show_date_picker(False),
    )
    ft.use_dialog(picker if user.is_admin and show_date_picker else None)

    async def search() -> None:
        async def operation() -> None:
            result = await _find_student(context.services, source, query, period)
            set_alumno(result.alumno)
            set_materias(result.materias)
            set_total_reprobadas(result.total_reprobadas)
            set_message("")
            set_is_error(False)

        try:
            await _run_guarded_request(search_gate, set_search_busy, operation)
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
        async def operation() -> None:
            output = await _create_pdf_workflow(
                page=ft.context.page,
                selector=FletPdfDestinationSelector(pdf_picker),
                services=context.services,
                alumno=alumno,
                dictaminacion=dictaminacion,
                director=director,
                materias=materias,
                ruling_unavailable=ruling_unavailable,
                reference=date.today(),
                fecha_sesion=fecha_sesion,
                on_post_mutation_failure=lambda _dictamen: (
                    set_alumno(None),
                    set_materias(()),
                    set_total_reprobadas(0),
                ),
            )
            set_message(output.message)
            set_is_error(not output.pdf_saved)

        try:
            await _run_guarded_request(
                create_gate,
                set_create_busy,
                operation,
            )
        except ValueError as error:
            set_message(str(error))
            set_is_error(True)
        except Exception as error:
            set_message(_creation_error_message(error))
            set_is_error(True)
            _redirect_expired_session(
                context,
                error,
                ft.context.page.navigate,
            )

    interaction_busy = search_busy or create_busy
    ruling_unavailable = _is_ruling_unavailable(
        source,
        alumno,
        materias,
        total_reprobadas,
    )

    student_card = ft.Container()
    if alumno:
        student_card = ft.Card(
            key="dictamen-student-result",
            content=ft.Container(
                padding=16,
                content=ft.Column(
                    [
                        ft.Text(alumno.nombre, size=20, weight=ft.FontWeight.BOLD),
                        ft.Text(f"Boleta: {alumno.boleta}"),
                        ft.Text(f"Carrera: {alumno.carrera}"),
                        _build_failed_subjects_section(
                            materias,
                            total_reprobadas,
                        )
                        if source == "reprobado"
                        else ft.Container(),
                    ]
                ),
            )
        )
    title, description = _page_copy(user)
    admin_controls = _admin_controls(
        user,
        (
            ft.TextField(
                label="Nombre del director",
                value=director,
                on_change=lambda e: set_director(e.control.value),
                disabled=create_busy,
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
                        disabled=create_busy,
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
                disabled=create_busy,
                key="dictamen-text",
            ),
            ft.Row(
                [
                    _build_create_button(
                        search_busy,
                        create_busy,
                        create,
                        ruling_unavailable=ruling_unavailable,
                    )
                ],
                alignment=ft.MainAxisAlignment.END,
            ),
        ),
    )
    return ft.Column(
        [
            page_header(title, description),
            ft.Dropdown(
                label="Origen de la búsqueda",
                value=source,
                options=[
                    ft.DropdownOption(key="inscrito", text="Alumno inscrito"),
                    ft.DropdownOption(key="reprobado", text="Alumno reprobado"),
                ],
                on_select=lambda e: _change_search_criterion(
                    e.control.value,
                    set_source,
                    set_alumno,
                    set_materias,
                    set_total_reprobadas,
                ),
                disabled=interaction_busy,
                key="dictamen-source",
            ),
            ft.Row(
                [
                    ft.TextField(
                        label="Número de boleta",
                        value=query,
                        on_change=lambda e: _change_search_criterion(
                            e.control.value,
                            set_query,
                            set_alumno,
                            set_materias,
                            set_total_reprobadas,
                        ),
                        disabled=interaction_busy,
                        expand=True,
                        key="dictamen-student-query",
                    ),
                    ft.TextField(
                        label="Periodo actual",
                        value=period,
                        on_change=lambda e: _change_search_criterion(
                            e.control.value,
                            set_period,
                            set_alumno,
                            set_materias,
                            set_total_reprobadas,
                        ),
                        width=170,
                        visible=source == "reprobado",
                        disabled=interaction_busy,
                        key="dictamen-current-period",
                    ),
                    ft.Button(
                        "Buscando..." if search_busy else "Buscar",
                        on_click=search,
                        disabled=interaction_busy,
                        key="dictamen-student-search",
                    ),
                ]
            ),
            feedback(message, error=is_error),
            student_card,
            *admin_controls,
        ],
        scroll=ft.ScrollMode.AUTO,
        expand=True,
    )
