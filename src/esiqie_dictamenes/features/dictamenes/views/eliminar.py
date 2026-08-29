from collections.abc import Callable, Sequence

import flet as ft

from esiqie_dictamenes.core.errors import (
    ApiConnectionError,
    ApiTimeoutError,
    NotFoundError,
    ValidationError,
    to_user_message,
)
from esiqie_dictamenes.core.routes import RoutePath
from esiqie_dictamenes.features.dictamenes.models import (
    Dictamen,
    DictamenFilter,
    DictamenPage,
)


def _selected_records(
    records: tuple[Dictamen, ...],
    selected_keys: frozenset[str],
) -> tuple[Dictamen, ...]:
    if not selected_keys:
        raise ValidationError("Selecciona al menos un dictamen para eliminar.")
    selected = tuple(
        record for record in records if record.clave in selected_keys
    )
    if len(selected) != len(selected_keys):
        raise NotFoundError()
    return selected


def _build_confirmation_dialog(
    records: Sequence[Dictamen],
    *,
    busy: bool,
    on_cancel: Callable,
    on_confirm: Callable,
) -> ft.AlertDialog:
    if len(records) == 1:
        question = f"¿Deseas eliminar el dictamen {records[0].clave}?"
    else:
        question = f"¿Deseas eliminar {len(records)} dictámenes?"
    return ft.AlertDialog(
        modal=True,
        title="Confirmar eliminación",
        content=ft.Column(
            [
                ft.Text(question),
                ft.Text("Esta acción no se puede deshacer."),
            ],
            tight=True,
        ),
        actions=[
            ft.Button(
                "Cancelar",
                on_click=on_cancel,
                disabled=busy,
                key="delete-cancel",
            ),
            ft.Button(
                "Eliminar",
                on_click=on_confirm,
                disabled=busy,
                key="delete-confirm",
            ),
        ],
    )


def _last_valid_page(total: int, limit: int) -> int:
    return max(1, (total + limit - 1) // limit)


def _target_page_after_delete(
    *,
    current_page: int,
    total_before: int,
    deleted: int,
    limit: int,
) -> int:
    remaining = max(0, total_before - deleted)
    return min(current_page, _last_valid_page(remaining, limit))


async def _reload_after_delete(
    controller,
    filters: DictamenFilter,
    *,
    current_page: int,
    total_before: int,
    deleted: int,
    limit: int,
) -> tuple[int, DictamenPage]:
    target_page = _target_page_after_delete(
        current_page=current_page,
        total_before=total_before,
        deleted=deleted,
        limit=limit,
    )
    result = await controller.search_page(filters, page=target_page)
    last_page = _last_valid_page(result.total, result.limit)
    if target_page > last_page:
        target_page = last_page
        result = await controller.search_page(filters, page=target_page)
    return target_page, result


async def _load_delete(
    controller,
    records: tuple[Dictamen, ...],
    *,
    require_admin: Callable[[], None],
) -> int:
    require_admin()
    return await controller.delete_dictamenes(records)


def _delete_success_message(deleted: int) -> str:
    if deleted == 1:
        return "1 dictamen eliminado correctamente."
    return f"{deleted} dictámenes eliminados correctamente."


def _delete_error_message(
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
        return (
            "Los dictámenes seleccionados cambiaron o ya no están disponibles. "
            "Actualiza la búsqueda."
        )
    if isinstance(error, (ApiTimeoutError, ApiConnectionError)):
        return (
            "No fue posible confirmar el resultado de la eliminación. "
            "Actualiza la búsqueda para verificar el estado."
        )
    return to_user_message(error)


def _refresh_error_message(
    context,
    error: Exception,
    navigate: Callable,
    *,
    deleted: int,
) -> str:
    if context.handle_session_error(error):
        navigate(RoutePath.LOGIN)
        return ""
    if deleted == 1:
        prefix = "Se eliminó 1 dictamen"
    else:
        prefix = f"Se eliminaron {deleted} dictámenes"
    return (
        f"{prefix}, pero no fue posible actualizar los resultados. "
        "Vuelve a buscar para confirmar el estado actual."
    )
