import asyncio
from datetime import date

import flet as ft
import pytest

from esiqie_dictamenes.core.context import AppContextValue
from esiqie_dictamenes.core.errors import (
    ApiConnectionError,
    ApiTimeoutError,
    AuthorizationError,
    NotFoundError,
    SessionExpiredError,
    ValidationError,
)
from esiqie_dictamenes.core.routes import RoutePath
from esiqie_dictamenes.features.dictamenes.models import Dictamen, DictamenPage
from esiqie_dictamenes.features.dictamenes.views import buscar, modificar
from tests.helpers import build_test_services


def _record(clave: str = "CSE-0001-26", text: str = "DICTAMEN ORIGINAL"):
    return Dictamen(
        clave=clave,
        boleta="2022630000",
        alumno="NOMBRE DEL ALUMNO",
        fecha=date(2026, 8, 26),
        anio=2026,
        dictaminacion=text,
    )


def _descendants(control):
    yield control
    for child in getattr(control, "controls", ()):
        yield from _descendants(child)
    content = getattr(control, "content", None)
    if isinstance(content, ft.Control):
        yield from _descendants(content)


def test_selection_requires_exactly_one_result_and_returns_domain_object():
    first = _record()
    second = _record("CSE-0002-26")

    with pytest.raises(ValidationError, match="Selecciona un dictamen"):
        buscar._selected_record((first, second), frozenset())
    with pytest.raises(ValidationError, match="únicamente"):
        buscar._selected_record(
            (first, second),
            frozenset((first.clave, second.clave)),
        )

    assert buscar._selected_record(
        (first, second),
        frozenset((second.clave,)),
    ) is second


def test_selection_toggle_preserves_other_selected_keys():
    selected = buscar._toggle_selected_key(
        frozenset(("CSE-0001-26",)),
        "CSE-0002-26",
        True,
    )

    assert selected == frozenset(("CSE-0001-26", "CSE-0002-26"))
    assert buscar._toggle_selected_key(
        selected,
        "CSE-0001-26",
        False,
    ) == frozenset(("CSE-0002-26",))


def test_results_table_uses_selectable_rows_without_action_column():
    record = _record()
    changes = []

    table_row = buscar._build_results_table(
        (record,),
        selected_keys=frozenset((record.clave,)),
        busy=False,
        on_selection=lambda key, selected: changes.append((key, selected)),
    )
    table = table_row.controls[0]
    row = table.rows[0]

    assert [column.label.value for column in table.columns] == [
        "Clave",
        "Boleta",
        "Alumno",
        "Año",
        "Dictaminación",
    ]
    assert table.show_checkbox_column is True
    assert row.data is record
    assert row.selected is True
    row.on_select_change(type("Event", (), {"control": row})())
    assert changes == [(record.clave, False)]


def test_results_cannot_change_selection_while_any_request_is_running():
    table_row = buscar._build_results_table(
        (_record(),),
        selected_keys=frozenset(),
        busy=True,
        on_selection=lambda _key, _selected: None,
    )

    row = table_row.controls[0].rows[0]
    assert row.disabled is True
    assert row.on_select_change is None


def test_edit_form_has_read_only_metadata_and_only_one_text_field():
    record = _record()
    form = modificar._build_edit_form(
        record=record,
        value=record.dictaminacion,
        busy=False,
        on_value=lambda _event: None,
        on_save=lambda: None,
        on_cancel=lambda: None,
    )
    controls = tuple(_descendants(form))
    fields = [control for control in controls if isinstance(control, ft.TextField)]
    texts = [control.value for control in controls if isinstance(control, ft.Text)]

    assert len(fields) == 1
    assert fields[0].label == "Dictaminación"
    assert fields[0].value == "DICTAMEN ORIGINAL"
    assert fields[0].read_only is False
    assert "Clave: CSE-0001-26" in texts
    assert "Boleta: 2022630000" in texts
    assert "Alumno: NOMBRE DEL ALUMNO" in texts
    assert "Fecha: 2026-08-26" in texts
    assert "Año: 2026" in texts


def test_edit_form_disables_field_and_actions_while_saving():
    form = modificar._build_edit_form(
        record=_record(),
        value="DICTAMEN ORIGINAL",
        busy=True,
        on_value=lambda _event: None,
        on_save=lambda: None,
        on_cancel=lambda: None,
    )
    controls = tuple(_descendants(form))

    assert all(
        control.disabled
        for control in controls
        if isinstance(control, (ft.TextField, ft.Button))
    )


def test_successful_update_replaces_only_current_page_item_and_keeps_pagination():
    first = _record()
    second = _record("CSE-0002-26")
    page = DictamenPage(total=347, skip=200, limit=100, items=(first, second))
    updated = _record(text="DICTAMEN ACTUALIZADO")

    result = buscar._replace_updated_record(page, updated)

    assert (result.total, result.skip, result.limit) == (347, 200, 100)
    assert result.items == (updated, second)
    assert result.items[1] is second


def test_update_commits_only_after_repository_success():
    current = _record()
    committed = []

    class FailingController:
        async def update_dictaminacion(self, record, value):
            raise ApiConnectionError()

    with pytest.raises(ApiConnectionError):
        asyncio.run(
            buscar._load_update(
                FailingController(),
                current,
                "NUEVO CONTENIDO",
                committed.append,
            )
        )

    assert committed == []


def test_unchanged_update_does_not_commit_a_false_success():
    current = _record()
    committed = []

    class UnchangedController:
        async def update_dictaminacion(self, record, value):
            return record

    changed = asyncio.run(
        buscar._load_update(
            UnchangedController(),
            current,
            "  DICTAMEN ORIGINAL  ",
            committed.append,
        )
    )

    assert changed is False
    assert committed == []


def test_update_guard_rejects_a_second_concurrent_save():
    async def scenario():
        gate = buscar._RequestGate()
        started = asyncio.Event()
        release = asyncio.Event()
        busy_states = []
        calls = 0

        async def operation():
            nonlocal calls
            calls += 1
            started.set()
            await release.wait()

        first = asyncio.create_task(
            buscar._run_guarded_request(gate, busy_states.append, operation)
        )
        await started.wait()
        second_result = await buscar._run_guarded_request(
            gate,
            busy_states.append,
            operation,
        )
        release.set()
        first_result = await first
        return calls, busy_states, first_result, second_result

    assert asyncio.run(scenario()) == (1, [True, False], True, False)


def test_expired_update_session_clears_tokens_and_navigates_to_login():
    services = build_test_services()
    session = services.auth_session.current
    assert session is not None
    session_updates = []
    routes = []
    cleared = []
    context = AppContextValue(
        services=services,
        session=session,
        set_session=session_updates.append,
    )

    message = buscar._update_error_message(
        context,
        SessionExpiredError(),
        routes.append,
        lambda: cleared.append(True),
    )

    assert message == ""
    assert services.auth_session.current is None
    assert session_updates == [None]
    assert routes == [RoutePath.LOGIN]
    assert cleared == []


def test_not_found_update_clears_selection_and_requests_refresh():
    cleared = []

    message = buscar._update_error_message(
        build_test_context(),
        NotFoundError(),
        lambda _route: None,
        lambda: cleared.append(True),
    )

    assert cleared == [True]
    assert message == (
        "El dictamen ya no está disponible. Actualiza la búsqueda."
    )


def test_forbidden_update_keeps_the_current_session():
    services = build_test_services()
    session = services.auth_session.current
    assert session is not None
    session_updates = []
    context = AppContextValue(
        services=services,
        session=session,
        set_session=session_updates.append,
    )

    message = buscar._update_error_message(
        context,
        AuthorizationError(),
        lambda _route: None,
        lambda: None,
    )

    assert "permiso" in message
    assert services.auth_session.current is session
    assert session_updates == []


@pytest.mark.parametrize("error", [ApiTimeoutError(), ApiConnectionError()])
def test_ambiguous_update_failure_does_not_invite_an_automatic_retry(error):
    message = buscar._update_error_message(
        build_test_context(),
        error,
        lambda _route: None,
        lambda: None,
    )

    assert message == (
        "No se pudo confirmar si el dictamen fue actualizado. "
        "Actualiza la búsqueda antes de intentarlo nuevamente."
    )


def build_test_context():
    services = build_test_services()
    session = services.auth_session.current
    assert session is not None
    return AppContextValue(
        services=services,
        session=session,
        set_session=lambda _session: None,
    )
