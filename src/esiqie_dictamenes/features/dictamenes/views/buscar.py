from collections.abc import Callable
from datetime import date
from inspect import isawaitable

import flet as ft

from esiqie_dictamenes.core.context import use_app_context
from esiqie_dictamenes.core.errors import (
    ApiConnectionError,
    ApiTimeoutError,
    AuthorizationError,
    NotFoundError,
    ValidationError,
    to_user_message,
)
from esiqie_dictamenes.core.routes import RoutePath
from esiqie_dictamenes.features.auth.models import AuthenticatedUser
from esiqie_dictamenes.features.dictamenes.models import (
    Dictamen,
    DictamenFilter,
    DictamenPage,
)
from esiqie_dictamenes.features.dictamenes.views.crear import (
    _as_date,
    _build_session_date_picker,
    _run_guarded_request,
)
from esiqie_dictamenes.features.dictamenes.views.eliminar import (
    _build_confirmation_dialog,
    _delete_error_message,
    _delete_success_message,
    _load_delete,
    _refresh_error_message,
    _reload_after_delete,
    _selected_records,
)
from esiqie_dictamenes.features.dictamenes.views.modificar import _build_edit_form
from esiqie_dictamenes.features.dictamenes.views.pdf_output import (
    FletPdfDestinationSelector,
    UpdatePdfResult,
    post_update_pdf_failure_message,
    require_desktop_pdf_output,
    selector_result,
    updated_pdf_message,
    use_file_picker,
)
from esiqie_dictamenes.shared.components.feedback import feedback
from esiqie_dictamenes.shared.components.page_header import page_header
from esiqie_dictamenes.shared.request_gate import RequestGate as _RequestGate


def _build_filter(criterion: str, query: str) -> DictamenFilter:
    normalized = query.strip()
    if not normalized:
        raise ValidationError("Escribe una boleta o un a\u00f1o.")
    if criterion == "boleta":
        return DictamenFilter(boleta=normalized)
    if criterion == "anio":
        try:
            return DictamenFilter(anio=int(normalized))
        except ValueError as error:
            raise ValidationError(
                "El a\u00f1o debe ser un n\u00famero v\u00e1lido."
            ) from error
    raise ValidationError(
        "Selecciona un criterio de b\u00fasqueda v\u00e1lido."
    )


def _pagination_labels(
    result: DictamenPage,
    *,
    current_page: int,
) -> tuple[str, str]:
    total_pages = (result.total + result.limit - 1) // result.limit
    first = result.skip + 1
    last = result.skip + len(result.items)
    return (
        f"P\u00e1gina {current_page} de {total_pages}",
        f"Mostrando {first}\u2013{last} de {result.total} dict\u00e1menes",
    )


def _search_success_message(result: DictamenPage) -> str:
    if result.total == 0:
        return "No se encontraron dict\u00e1menes"
    return f"{result.total} dictamen(es) encontrado(s)."


async def _load_page(
    controller,
    filters: DictamenFilter,
    page: int,
    commit: Callable[[DictamenFilter, int, DictamenPage], None],
) -> None:
    result = await controller.search_page(filters, page=page)
    commit(filters, page, result)


def _search_error_message(context, error: Exception, navigate: Callable) -> str:
    if context.handle_session_error(error):
        navigate(RoutePath.LOGIN)
        return ""
    return to_user_message(error)


def _toggle_selected_key(
    selected_keys: frozenset[str],
    clave: str,
    selected: bool,
) -> frozenset[str]:
    if selected:
        return selected_keys | {clave}
    return selected_keys - {clave}


def _selected_record(
    records: tuple[Dictamen, ...],
    selected_keys: frozenset[str],
) -> Dictamen:
    if not selected_keys:
        raise ValidationError("Selecciona un dictamen para modificar.")
    if len(selected_keys) > 1:
        raise ValidationError(
            "Selecciona únicamente un dictamen para modificar."
        )
    selected_key = next(iter(selected_keys))
    for record in records:
        if record.clave == selected_key:
            return record
    raise NotFoundError()


def _replace_updated_record(
    page: DictamenPage,
    updated: Dictamen,
) -> DictamenPage:
    if all(record.clave != updated.clave for record in page.items):
        raise NotFoundError()
    return DictamenPage(
        total=page.total,
        skip=page.skip,
        limit=page.limit,
        items=tuple(
            updated if record.clave == updated.clave else record
            for record in page.items
        ),
    )


async def _update_pdf_workflow(
    *,
    page,
    selector,
    services,
    current: Dictamen,
    dictaminacion: str,
    director: str,
    fecha_sesion: date,
    commit: Callable[[Dictamen], None],
) -> UpdatePdfResult:
    """Run UPDATE's destination, mutation, generation, and save stages."""
    services.auth_session.require_admin()
    if not isinstance(dictaminacion, str) or not dictaminacion.strip():
        raise ValueError("La dictaminación es obligatoria.")
    normalized = dictaminacion.strip()
    if not isinstance(director, str) or not director.strip():
        raise ValueError("El director es obligatorio.")
    if not isinstance(fecha_sesion, date):
        raise ValueError("Selecciona la fecha de sesión en el calendario.")
    if normalized == current.dictaminacion:
        return UpdatePdfResult(
            updated=None,
            no_op=True,
            message="No hay cambios por guardar.",
        )

    require_desktop_pdf_output(page)
    selected = selector_result(selector, current)
    if isawaitable(selected):
        selected = await selected
    if not selected:
        return UpdatePdfResult(updated=None, cancelled=True)

    destination = services.document_store.validate_destination(selected)
    updated = await services.dictamen_controller.update_dictaminacion(
        current,
        normalized,
    )
    commit(updated)

    try:
        request = services.dictamen_controller.prepare_updated_pdf_request(
            updated,
            director=director,
            fecha_sesion=fecha_sesion,
        )
        document = await services.dictamen_controller.generate_pdf(request)
        saved_path = await services.document_store.save(
            destination,
            document.content,
        )
    except Exception:
        return UpdatePdfResult(
            updated=updated,
            pdf_saved=False,
            message=post_update_pdf_failure_message(updated.clave, destination),
        )

    return UpdatePdfResult(
        updated=updated,
        saved_path=saved_path,
        pdf_saved=True,
        message=updated_pdf_message(updated.clave, saved_path),
    )


def _consume_update_pdf_result(
    result: UpdatePdfResult,
    set_message: Callable[[str], None],
    set_has_error: Callable[[bool], None],
) -> None:
    """Apply a completed update workflow result to the visible feedback state."""
    if result.cancelled:
        return
    set_message(result.message)
    set_has_error(not result.pdf_saved and not result.no_op)


async def _load_update(
    controller,
    current: Dictamen,
    value: str,
    commit: Callable[[Dictamen], None],
    *,
    require_admin: Callable[[], None],
) -> bool:
    require_admin()
    updated = await controller.update_dictaminacion(current, value)
    if updated == current:
        return False
    commit(updated)
    return True


def _run_admin_action(
    require_admin: Callable[[], None],
    action: Callable[[], None],
) -> None:
    require_admin()
    action()


def _update_error_message(
    context,
    error: Exception,
    navigate: Callable,
    clear_selection: Callable[[], None],
) -> str:
    if context.handle_session_error(error):
        navigate(RoutePath.LOGIN)
        return ""
    if isinstance(error, NotFoundError):
        clear_selection()
        return "El dictamen ya no está disponible. Actualiza la búsqueda."
    if isinstance(error, (ApiTimeoutError, ApiConnectionError)):
        return (
            "No se pudo confirmar si el dictamen fue actualizado. "
            "Actualiza la búsqueda antes de intentarlo nuevamente."
        )
    return to_user_message(error)


def _build_search_controls(
    *,
    criterion: str,
    query: str,
    busy: bool,
    on_criterion: Callable,
    on_query: Callable,
    on_search: Callable,
) -> ft.Row:
    return ft.Row(
        [
            ft.Dropdown(
                label="Criterio",
                value=criterion,
                options=[
                    ft.DropdownOption(
                        key="boleta",
                        text="N\u00famero de boleta",
                    ),
                    ft.DropdownOption(key="anio", text="A\u00f1o"),
                ],
                on_select=on_criterion,
                disabled=busy,
                width=220,
                key="dictamen-criterion",
            ),
            ft.TextField(
                label="Valor de b\u00fasqueda",
                value=query,
                on_change=on_query,
                on_submit=on_search,
                disabled=busy,
                expand=True,
                key="dictamen-query",
            ),
            ft.Button(
                "Buscar",
                on_click=on_search,
                disabled=busy,
                key="dictamen-search",
            ),
        ]
    )


def _build_results_table(
    records: tuple[Dictamen, ...],
    user: AuthenticatedUser,
    *,
    selected_keys: frozenset[str],
    busy: bool,
    on_selection: Callable[[str, bool], None],
) -> ft.Control:
    if not records:
        return ft.Container()
    return ft.Row(
        [
            ft.DataTable(
                show_checkbox_column=user.is_admin,
                columns=[
                    ft.DataColumn(ft.Text("Clave")),
                    ft.DataColumn(ft.Text("Boleta")),
                    ft.DataColumn(ft.Text("Alumno")),
                    ft.DataColumn(ft.Text("A\u00f1o")),
                    ft.DataColumn(ft.Text("Dictaminaci\u00f3n")),
                ],
                rows=[
                    ft.DataRow(
                        data=record,
                        selected=(
                            user.is_admin and record.clave in selected_keys
                        ),
                        disabled=busy,
                        on_select_change=(
                            None
                            if busy or not user.is_admin
                            else lambda _event, key=record.clave, selected=(
                                record.clave in selected_keys
                            ): on_selection(key, not selected)
                        ),
                        cells=[
                            ft.DataCell(ft.Text(record.clave)),
                            ft.DataCell(ft.Text(record.boleta)),
                            ft.DataCell(ft.Text(record.alumno)),
                            ft.DataCell(ft.Text(str(record.anio))),
                            ft.DataCell(ft.Text(record.dictaminacion)),
                        ]
                    )
                    for record in records
                ],
            )
        ],
        scroll=ft.ScrollMode.AUTO,
    )


def _build_selection_actions(
    user: AuthenticatedUser,
    *,
    busy: bool,
    has_results: bool,
    editing: bool,
    selected_count: int = 0,
    on_edit: Callable,
    on_delete: Callable | None = None,
) -> ft.Control:
    if not user.is_admin:
        return ft.Container()
    delete_label = "Eliminar seleccionados"
    if selected_count == 1:
        delete_label = "Eliminar seleccionado"
    elif selected_count > 1:
        delete_label = f"Eliminar {selected_count} seleccionados"
    return ft.Row(
        [
            ft.Button(
                "Modificar seleccionado",
                on_click=on_edit,
                disabled=busy or not has_results or editing,
                key="dictamen-edit-selected",
            ),
            ft.Button(
                delete_label,
                on_click=on_delete,
                disabled=busy or not has_results or editing,
                key="dictamen-delete-selected",
            ),
        ],
        alignment=ft.MainAxisAlignment.END,
    )


@ft.component
def DictamenSearchView() -> ft.Control:
    context = use_app_context()
    user = context.session.current_user
    assert user is not None
    gate = ft.use_memo(_RequestGate, [])
    criterion, set_criterion = ft.use_state("boleta")
    query, set_query = ft.use_state("")
    committed_filter, set_committed_filter = ft.use_state(None)
    current_page, set_current_page = ft.use_state(1)
    result, set_result = ft.use_state(None)
    selected_keys, set_selected_keys = ft.use_state(frozenset())
    pending_delete, set_pending_delete = ft.use_state(())
    editing_record, set_editing_record = ft.use_state(None)
    edit_value, set_edit_value = ft.use_state("")
    edit_director, set_edit_director = ft.use_state("")
    edit_fecha_sesion, set_edit_fecha_sesion = ft.use_state(date.today())
    show_edit_date_picker, set_show_edit_date_picker = ft.use_state(False)
    busy, set_busy = ft.use_state(False)
    message, set_message = ft.use_state("")
    has_error, set_has_error = ft.use_state(False)
    pdf_picker = use_file_picker()

    def clear_selection() -> None:
        set_selected_keys(frozenset())
        set_pending_delete(())
        set_editing_record(None)
        set_edit_value("")
        set_edit_director("")
        set_edit_fecha_sesion(date.today())
        set_show_edit_date_picker(False)

    def select_edit_session_date(event: ft.Event[ft.DatePicker]) -> None:
        if event.control.value is not None:
            set_edit_fecha_sesion(_as_date(event.control.value))
        set_show_edit_date_picker(False)

    edit_date_picker = _build_session_date_picker(
        edit_fecha_sesion,
        on_change=select_edit_session_date,
        on_dismiss=lambda _event: set_show_edit_date_picker(False),
    )
    edit_date_dialog = (
        edit_date_picker
        if user.is_admin and editing_record is not None and show_edit_date_picker
        else None
    )

    def commit_page(
        filters: DictamenFilter,
        page: int,
        loaded: DictamenPage,
    ) -> None:
        set_committed_filter(filters)
        set_current_page(page)
        set_result(loaded)
        clear_selection()
        set_message(_search_success_message(loaded))
        set_has_error(False)

    async def request_page(
        filters: DictamenFilter,
        page: int,
        *,
        reset_results: bool = False,
    ) -> None:
        async def operation() -> None:
            if reset_results:
                set_result(None)
                set_committed_filter(None)
                set_current_page(1)
                clear_selection()
                set_message("")
            try:
                await _load_page(
                    context.services.dictamen_controller,
                    filters,
                    page,
                    commit_page,
                )
            except Exception as error:
                set_message(
                    _search_error_message(
                        context,
                        error,
                        ft.context.page.navigate,
                    )
                )
                set_has_error(True)

        await _run_guarded_request(gate, set_busy, operation)

    async def search() -> None:
        try:
            filters = _build_filter(criterion, query)
        except ValidationError as error:
            set_message(to_user_message(error))
            set_has_error(True)
            return
        await request_page(filters, 1, reset_results=True)

    async def previous_page() -> None:
        if committed_filter is not None and current_page > 1:
            await request_page(committed_filter, current_page - 1)

    async def next_page() -> None:
        if result is None or committed_filter is None:
            return
        total_pages = (result.total + result.limit - 1) // result.limit
        if current_page < total_pages:
            await request_page(committed_filter, current_page + 1)

    def change_selection(clave: str, selected: bool) -> None:
        set_selected_keys(_toggle_selected_key(selected_keys, clave, selected))

    def open_editor() -> None:
        def action() -> None:
            selected = _selected_record(records, selected_keys)
            set_editing_record(selected)
            set_edit_value(selected.dictaminacion)
            set_edit_director("")
            set_edit_fecha_sesion(date.today())
            set_message("")
            set_has_error(False)

        try:
            _run_admin_action(
                context.services.auth_session.require_admin,
                action,
            )
        except (AuthorizationError, ValidationError, NotFoundError) as error:
            set_message(to_user_message(error))
            set_has_error(True)

    def open_delete_confirmation() -> None:
        def action() -> None:
            selected = _selected_records(records, selected_keys)
            set_pending_delete(selected)
            set_message("")
            set_has_error(False)

        try:
            _run_admin_action(
                context.services.auth_session.require_admin,
                action,
            )
        except (AuthorizationError, ValidationError, NotFoundError) as error:
            set_message(to_user_message(error))
            set_has_error(True)

    def commit_update(updated: Dictamen) -> None:
        if result is None:
            raise NotFoundError()
        set_result(_replace_updated_record(result, updated))
        clear_selection()
        set_message("Dictamen actualizado correctamente.")
        set_has_error(False)

    async def save_update() -> None:
        if editing_record is None:
            return

        async def operation() -> None:
            try:
                output = await _update_pdf_workflow(
                    page=ft.context.page,
                    selector=FletPdfDestinationSelector(pdf_picker),
                    services=context.services,
                    current=editing_record,
                    dictaminacion=edit_value,
                    director=edit_director,
                    fecha_sesion=edit_fecha_sesion,
                    commit=commit_update,
                )
                _consume_update_pdf_result(output, set_message, set_has_error)
            except ValueError as error:
                set_message(str(error))
                set_has_error(True)
            except Exception as error:
                set_message(
                    _update_error_message(
                        context,
                        error,
                        ft.context.page.navigate,
                        clear_selection,
                    )
                )
                set_has_error(True)

        await _run_guarded_request(gate, set_busy, operation)

    async def confirm_delete() -> None:
        if (
            not pending_delete
            or result is None
            or committed_filter is None
        ):
            return
        selected = pending_delete
        current_result = result
        filters = committed_filter
        page = current_page

        async def operation() -> None:
            try:
                deleted = await _load_delete(
                    context.services.dictamen_controller,
                    selected,
                    require_admin=(
                        context.services.auth_session.require_admin
                    ),
                )
            except Exception as error:
                set_pending_delete(())
                set_message(
                    _delete_error_message(
                        context,
                        error,
                        ft.context.page.navigate,
                        clear_selection,
                    )
                )
                set_has_error(True)
                return

            clear_selection()
            set_result(None)
            try:
                target_page, loaded = await _reload_after_delete(
                    context.services.dictamen_controller,
                    filters,
                    current_page=page,
                    total_before=current_result.total,
                    deleted=deleted,
                    limit=current_result.limit,
                )
            except Exception as error:
                set_message(
                    _refresh_error_message(
                        context,
                        error,
                        ft.context.page.navigate,
                        deleted=deleted,
                    )
                )
                set_has_error(True)
                return

            set_committed_filter(filters)
            set_current_page(target_page)
            set_result(loaded)
            set_message(_delete_success_message(deleted))
            set_has_error(False)

        await _run_guarded_request(gate, set_busy, operation)

    delete_dialog = None
    if user.is_admin and pending_delete:
        delete_dialog = _build_confirmation_dialog(
            pending_delete,
            busy=busy,
            on_cancel=lambda: set_pending_delete(()),
            on_confirm=confirm_delete,
        )
    ft.use_dialog(delete_dialog or edit_date_dialog)

    pagination = ft.Container()
    records = ()
    if result is not None:
        records = result.items
        if result.total > 0:
            page_label, range_label = _pagination_labels(
                result,
                current_page=current_page,
            )
            total_pages = (result.total + result.limit - 1) // result.limit
            pagination = ft.Column(
                [
                    ft.Text(range_label),
                    ft.Row(
                        [
                            ft.Button(
                                "Anterior",
                                on_click=previous_page,
                                disabled=busy or current_page <= 1,
                                key="dictamen-previous",
                            ),
                            ft.Text(page_label),
                            ft.Button(
                                "Siguiente",
                                on_click=next_page,
                                disabled=busy or current_page >= total_pages,
                                key="dictamen-next",
                            ),
                        ]
                    ),
                ]
            )

    edit_form = ft.Container()
    if user.is_admin and editing_record is not None:
        edit_form = ft.Container(
            content=_build_edit_form(
                record=editing_record,
                value=edit_value,
                director=edit_director,
                fecha_sesion=edit_fecha_sesion,
                busy=busy,
                on_value=lambda event: set_edit_value(event.control.value),
                on_director=lambda event: set_edit_director(event.control.value),
                on_date=lambda: set_show_edit_date_picker(True),
                on_save=save_update,
                on_cancel=clear_selection,
            ),
            padding=20,
            border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=12,
        )

    return ft.Column(
        [
            page_header(
                "Buscar dict\u00e1menes",
                "Consulta por n\u00famero de boleta o a\u00f1o.",
            ),
            _build_search_controls(
                criterion=criterion,
                query=query,
                busy=busy,
                on_criterion=lambda event: set_criterion(event.control.value),
                on_query=lambda event: set_query(event.control.value),
                on_search=search,
            ),
            ft.ProgressRing(visible=busy),
            feedback(message, error=has_error),
            _build_results_table(
                records,
                user,
                selected_keys=selected_keys,
                busy=busy,
                on_selection=change_selection,
            ),
            _build_selection_actions(
                user,
                busy=busy,
                has_results=bool(records),
                editing=editing_record is not None,
                selected_count=len(selected_keys),
                on_edit=open_editor,
                on_delete=open_delete_confirmation,
            ),
            edit_form,
            pagination,
        ],
        scroll=ft.ScrollMode.AUTO,
        expand=True,
    )
