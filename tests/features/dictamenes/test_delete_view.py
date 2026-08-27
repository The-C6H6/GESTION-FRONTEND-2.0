import asyncio
from datetime import date

import flet as ft
import pytest

from esiqie_dictamenes.core.context import AppContextValue
from esiqie_dictamenes.core.errors import (
    ApiConnectionError,
    ApiTimeoutError,
    NotFoundError,
    SessionExpiredError,
    ValidationError,
)
from esiqie_dictamenes.core.routes import RoutePath
from esiqie_dictamenes.core.services import build_demo_services
from esiqie_dictamenes.features.auth.models import Session
from esiqie_dictamenes.features.dictamenes.models import (
    Dictamen,
    DictamenFilter,
    DictamenPage,
)
from esiqie_dictamenes.features.dictamenes.views import buscar, eliminar


def _record(clave: str) -> Dictamen:
    return Dictamen(
        clave=clave,
        boleta="2022630000",
        alumno="NOMBRE DEL ALUMNO",
        fecha=date(2026, 8, 26),
        anio=2026,
        dictaminacion="DICTAMEN ORIGINAL",
    )


def _descendants(control):
    yield control
    for child in getattr(control, "controls", ()):
        yield from _descendants(child)
    content = getattr(control, "content", None)
    if isinstance(content, ft.Control):
        yield from _descendants(content)


def _context():
    return AppContextValue(
        services=build_demo_services(),
        session=Session("directivo", is_admin=False, is_demo=True),
        set_session=lambda _session: None,
    )


def test_delete_selection_returns_domain_entities_in_page_order():
    first = _record("CSE-0001-26")
    second = _record("CSE-0002-26")

    selected = eliminar._selected_records(
        (first, second),
        frozenset((second.clave, first.clave)),
    )

    assert selected == (first, second)
    assert selected[0] is first
    assert selected[1] is second


def test_delete_selection_rejects_empty_and_stale_keys():
    record = _record("CSE-0001-26")

    with pytest.raises(ValidationError, match="Selecciona al menos"):
        eliminar._selected_records((record,), frozenset())
    with pytest.raises(NotFoundError):
        eliminar._selected_records((record,), frozenset(("CSE-STALE-26",)))


@pytest.mark.parametrize(
    ("records", "expected_question"),
    [
        (
            (_record("CSE-0001-26"),),
            "¿Deseas eliminar el dictamen CSE-0001-26?",
        ),
        (
            (_record("CSE-0001-26"), _record("CSE-0002-26")),
            "¿Deseas eliminar 2 dictámenes?",
        ),
    ],
)
def test_delete_confirmation_is_explicit_and_describes_the_selection(
    records,
    expected_question,
):
    calls = []
    dialog = eliminar._build_confirmation_dialog(
        records,
        busy=False,
        on_cancel=lambda: calls.append("cancel"),
        on_confirm=lambda: calls.append("confirm"),
    )
    texts = [
        control.value
        for control in _descendants(dialog)
        if isinstance(control, ft.Text)
    ]

    assert dialog.modal is True
    assert expected_question in texts
    assert "Esta acción no se puede deshacer." in texts
    assert [action.key for action in dialog.actions] == [
        "delete-cancel",
        "delete-confirm",
    ]
    assert calls == []


def test_delete_confirmation_actions_are_disabled_while_request_is_running():
    dialog = eliminar._build_confirmation_dialog(
        (_record("CSE-0001-26"),),
        busy=True,
        on_cancel=lambda: None,
        on_confirm=lambda: None,
    )

    assert all(action.disabled for action in dialog.actions)


def test_cancel_confirmation_does_not_invoke_delete():
    calls = []
    dialog = eliminar._build_confirmation_dialog(
        (_record("CSE-0001-26"),),
        busy=False,
        on_cancel=lambda: calls.append("cancel"),
        on_confirm=lambda: calls.append("delete"),
    )

    dialog.actions[0].on_click()

    assert calls == ["cancel"]


@pytest.mark.parametrize(
    ("current_page", "total_before", "deleted", "expected_page"),
    [
        (1, 50, 1, 1),
        (3, 250, 30, 3),
        (3, 201, 1, 2),
        (4, 301, 1, 3),
        (1, 1, 1, 1),
    ],
)
def test_delete_target_page_never_exceeds_the_confirmed_remaining_pages(
    current_page,
    total_before,
    deleted,
    expected_page,
):
    assert eliminar._target_page_after_delete(
        current_page=current_page,
        total_before=total_before,
        deleted=deleted,
        limit=100,
    ) == expected_page


def test_delete_reload_preserves_filter_and_current_page_when_still_valid():
    loaded = DictamenPage(
        total=220,
        skip=200,
        limit=100,
        items=(_record("CSE-0201-26"),),
    )

    class Controller:
        def __init__(self):
            self.calls = []

        async def search_page(self, filters, *, page):
            self.calls.append((filters, page))
            return loaded

    controller = Controller()
    filters = DictamenFilter(anio=2026)

    page, result = asyncio.run(
        eliminar._reload_after_delete(
            controller,
            filters,
            current_page=3,
            total_before=250,
            deleted=30,
            limit=100,
        )
    )

    assert (page, result) == (3, loaded)
    assert controller.calls == [(filters, 3)]


def test_delete_reload_falls_back_again_when_concurrent_changes_remove_page():
    stale_page = DictamenPage(total=100, skip=200, limit=100, items=())
    valid_page = DictamenPage(
        total=100,
        skip=0,
        limit=100,
        items=(_record("CSE-0001-26"),),
    )

    class Controller:
        def __init__(self):
            self.pages = []

        async def search_page(self, filters, *, page):
            self.pages.append(page)
            return stale_page if page == 3 else valid_page

    controller = Controller()

    page, result = asyncio.run(
        eliminar._reload_after_delete(
            controller,
            DictamenFilter(boleta="2022630000"),
            current_page=3,
            total_before=350,
            deleted=1,
            limit=100,
        )
    )

    assert (page, result) == (1, valid_page)
    assert controller.pages == [3, 1]


def test_delete_request_receives_only_selected_domain_entities():
    selected = (_record("CSE-0001-26"), _record("CSE-0003-26"))

    class Controller:
        def __init__(self):
            self.received = None

        async def delete_dictamenes(self, records):
            self.received = records
            return len(records)

    controller = Controller()

    total = asyncio.run(eliminar._load_delete(controller, selected))

    assert total == 2
    assert controller.received is selected


def test_delete_gate_rejects_a_second_concurrent_confirmation():
    selected = (_record("CSE-0001-26"),)

    class Controller:
        def __init__(self):
            self.calls = 0
            self.started = asyncio.Event()
            self.release = asyncio.Event()

        async def delete_dictamenes(self, records):
            self.calls += 1
            self.started.set()
            await self.release.wait()
            return len(records)

    async def scenario():
        controller = Controller()
        gate = buscar._RequestGate()
        busy_states = []

        async def operation():
            await eliminar._load_delete(controller, selected)

        first = asyncio.create_task(
            buscar._run_guarded_request(gate, busy_states.append, operation)
        )
        await controller.started.wait()
        second = await buscar._run_guarded_request(
            gate,
            busy_states.append,
            operation,
        )
        controller.release.set()
        first_result = await first
        return controller.calls, busy_states, first_result, second

    assert asyncio.run(scenario()) == (1, [True, False], True, False)


@pytest.mark.parametrize(
    ("deleted", "expected"),
    [
        (1, "1 dictamen eliminado correctamente."),
        (3, "3 dictámenes eliminados correctamente."),
    ],
)
def test_delete_success_message_uses_the_confirmed_backend_total(
    deleted,
    expected,
):
    assert eliminar._delete_success_message(deleted) == expected


@pytest.mark.parametrize("error", [ApiTimeoutError(), ApiConnectionError()])
def test_ambiguous_delete_failure_does_not_change_selection_or_invite_retry(error):
    cleared = []

    message = eliminar._delete_error_message(
        _context(),
        error,
        lambda _route: None,
        lambda: cleared.append(True),
    )

    assert message == (
        "No fue posible confirmar el resultado de la eliminación. "
        "Actualiza la búsqueda para verificar el estado."
    )
    assert cleared == []


def test_not_found_delete_clears_stale_selection_without_assuming_success():
    cleared = []

    message = eliminar._delete_error_message(
        _context(),
        NotFoundError(),
        lambda _route: None,
        lambda: cleared.append(True),
    )

    assert cleared == [True]
    assert message == (
        "Los dictámenes seleccionados cambiaron o ya no están disponibles. "
        "Actualiza la búsqueda."
    )


def test_expired_delete_session_clears_tokens_and_redirects_to_login():
    services = build_demo_services()
    services.auth_tokens.replace("expired-access", "expired-refresh")
    session_updates = []
    routes = []
    context = AppContextValue(
        services=services,
        session=Session("directivo", is_admin=False, is_demo=False),
        set_session=session_updates.append,
    )

    message = eliminar._delete_error_message(
        context,
        SessionExpiredError(),
        routes.append,
        lambda: None,
    )

    assert message == ""
    assert services.auth_tokens.has_tokens is False
    assert session_updates == [None]
    assert routes == [RoutePath.LOGIN]


@pytest.mark.parametrize(
    ("deleted", "prefix"),
    [
        (1, "Se eliminó 1 dictamen"),
        (2, "Se eliminaron 2 dictámenes"),
    ],
)
def test_confirmed_delete_refresh_failure_reports_confirmed_delete_separately(
    deleted,
    prefix,
):
    message = eliminar._refresh_error_message(
        _context(),
        ApiConnectionError(),
        lambda _route: None,
        deleted=deleted,
    )

    assert message == (
        f"{prefix}, pero no fue posible actualizar los "
        "resultados. Vuelve a buscar para confirmar el estado actual."
    )


def test_selection_actions_offer_modify_and_delete_without_immediate_request():
    calls = []

    actions = buscar._build_selection_actions(
        busy=False,
        has_results=True,
        editing=False,
        selected_count=2,
        on_edit=lambda: calls.append("edit"),
        on_delete=lambda: calls.append("delete"),
    )

    assert [control.key for control in actions.controls] == [
        "dictamen-edit-selected",
        "dictamen-delete-selected",
    ]
    assert actions.controls[1].content == "Eliminar 2 seleccionados"
    assert calls == []


def test_delete_and_modify_actions_are_disabled_during_any_request():
    actions = buscar._build_selection_actions(
        busy=True,
        has_results=True,
        editing=False,
        selected_count=1,
        on_edit=lambda: None,
        on_delete=lambda: None,
    )

    assert all(control.disabled for control in actions.controls)
