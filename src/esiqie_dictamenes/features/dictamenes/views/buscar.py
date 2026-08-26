from collections.abc import Callable

import flet as ft

from esiqie_dictamenes.core.context import use_app_context
from esiqie_dictamenes.core.errors import ValidationError, to_user_message
from esiqie_dictamenes.core.routes import RoutePath
from esiqie_dictamenes.features.dictamenes.models import (
    DictamenFilter,
    DictamenPage,
)
from esiqie_dictamenes.features.dictamenes.views.crear import (
    _RequestGate,
    _run_guarded_request,
)
from esiqie_dictamenes.shared.components.feedback import feedback
from esiqie_dictamenes.shared.components.page_header import page_header


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


def _build_results_table(records: tuple, *, busy: bool = False) -> ft.Control:
    if not records:
        return ft.Container()
    return ft.Row(
        [
            ft.DataTable(
                columns=[
                    ft.DataColumn(ft.Text("Clave")),
                    ft.DataColumn(ft.Text("Boleta")),
                    ft.DataColumn(ft.Text("Alumno")),
                    ft.DataColumn(ft.Text("A\u00f1o")),
                    ft.DataColumn(ft.Text("Dictaminaci\u00f3n")),
                    ft.DataColumn(ft.Text("Acci\u00f3n")),
                ],
                rows=[
                    ft.DataRow(
                        cells=[
                            ft.DataCell(ft.Text(record.clave)),
                            ft.DataCell(ft.Text(record.boleta)),
                            ft.DataCell(ft.Text(record.alumno)),
                            ft.DataCell(ft.Text(str(record.anio))),
                            ft.DataCell(ft.Text(record.dictaminacion)),
                            ft.DataCell(
                                ft.Button(
                                    "Modificar",
                                    on_click=lambda _event, key=record.clave: ft.context.page.navigate(
                                        f"/dictamenes/{key}/editar"
                                    ),
                                    disabled=busy,
                                )
                            ),
                        ]
                    )
                    for record in records
                ],
            )
        ],
        scroll=ft.ScrollMode.AUTO,
    )


@ft.component
def DictamenSearchView() -> ft.Control:
    context = use_app_context()
    gate = ft.use_memo(_RequestGate, [])
    criterion, set_criterion = ft.use_state("boleta")
    query, set_query = ft.use_state("")
    committed_filter, set_committed_filter = ft.use_state(None)
    current_page, set_current_page = ft.use_state(1)
    result, set_result = ft.use_state(None)
    busy, set_busy = ft.use_state(False)
    message, set_message = ft.use_state("")
    has_error, set_has_error = ft.use_state(False)

    def commit_page(
        filters: DictamenFilter,
        page: int,
        loaded: DictamenPage,
    ) -> None:
        set_committed_filter(filters)
        set_current_page(page)
        set_result(loaded)
        set_message(_search_success_message(loaded))
        set_has_error(False)

    async def request_page(filters: DictamenFilter, page: int) -> None:
        async def operation() -> None:
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
        await request_page(filters, 1)

    async def previous_page() -> None:
        if committed_filter is not None and current_page > 1:
            await request_page(committed_filter, current_page - 1)

    async def next_page() -> None:
        if result is None or committed_filter is None:
            return
        total_pages = (result.total + result.limit - 1) // result.limit
        if current_page < total_pages:
            await request_page(committed_filter, current_page + 1)

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
            feedback(message, error=has_error),
            _build_results_table(records, busy=busy),
            pagination,
        ],
        scroll=ft.ScrollMode.AUTO,
        expand=True,
    )
