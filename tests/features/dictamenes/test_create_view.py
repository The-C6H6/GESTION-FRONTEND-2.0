import asyncio
from datetime import date, datetime
from types import SimpleNamespace

import flet as ft
import pytest

from esiqie_dictamenes.core.context import AppContextValue
from esiqie_dictamenes.core.errors import AuthorizationError, SessionExpiredError
from esiqie_dictamenes.core.routes import RoutePath
from esiqie_dictamenes.core.services import build_demo_services
from esiqie_dictamenes.features.auth.models import Session
from esiqie_dictamenes.features.dictamenes.models import MateriaElegible
from esiqie_dictamenes.features.dictamenes.views import crear


def test_session_picker_only_allows_calendar_selection():
    selected = date(2026, 12, 11)

    picker = crear._build_session_date_picker(
        selected,
        on_change=lambda _event: None,
        on_dismiss=lambda _event: None,
    )

    assert isinstance(picker, ft.DatePicker)
    assert picker.entry_mode == ft.DatePickerEntryMode.CALENDAR_ONLY
    assert picker.value == selected
    assert picker.locale == ft.Locale("es", "MX")


def test_picker_datetime_is_normalized_to_a_date_object():
    result = crear._as_date(datetime(2026, 12, 11, 18, 30))

    assert result == date(2026, 12, 11)
    assert type(result) is date


def test_failed_subject_search_uses_the_selected_enrolled_student():
    selected_student = SimpleNamespace(boleta="2024320678")
    candidate = SimpleNamespace(
        alumno=selected_student,
        materias=(MateriaElegible("Cálculo", 20252, 19),),
        total_reprobadas=1,
    )

    class AlumnoControllerSpy:
        def __init__(self):
            self.queries = []

        async def find_inscrito(self, query):
            self.queries.append(query)
            return selected_student

    class DictamenControllerSpy:
        def __init__(self):
            self.calls = []

        async def find_reprobado_candidate_for_student(self, alumno, period):
            self.calls.append((alumno, period))
            return candidate

    alumno_controller = AlumnoControllerSpy()
    dictamen_controller = DictamenControllerSpy()
    services = SimpleNamespace(
        alumno_controller=alumno_controller,
        dictamen_controller=dictamen_controller,
    )

    result = asyncio.run(
        crear._find_student(services, "reprobado", "2024320678", "20271")
    )

    assert alumno_controller.queries == ["2024320678"]
    assert dictamen_controller.calls == [(selected_student, "20271")]
    assert result.alumno is selected_student
    assert result.total_reprobadas == 1


def test_search_guard_rejects_a_second_concurrent_operation():
    async def scenario():
        gate = crear._RequestGate()
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
            crear._run_guarded_search(gate, busy_states.append, operation)
        )
        await started.wait()
        second_result = await crear._run_guarded_search(
            gate, busy_states.append, operation
        )
        release.set()
        first_result = await first
        return calls, busy_states, first_result, second_result

    calls, busy_states, first_result, second_result = asyncio.run(scenario())

    assert calls == 1
    assert busy_states == [True, False]
    assert first_result is True
    assert second_result is False


def test_search_guard_always_restores_loading_after_an_exception():
    async def failing_operation():
        raise RuntimeError("network failed")

    gate = crear._RequestGate()
    busy_states = []

    with pytest.raises(RuntimeError, match="network failed"):
        asyncio.run(
            crear._run_guarded_search(gate, busy_states.append, failing_operation)
        )

    assert busy_states == [True, False]
    assert gate.active is False


def test_expired_session_clears_tokens_and_navigates_to_login():
    services = build_demo_services()
    services.auth_tokens.replace("expired-access", "expired-refresh")
    session_updates = []
    routes = []
    context = AppContextValue(
        services=services,
        session=Session("directivo", is_admin=False, is_demo=False),
        set_session=session_updates.append,
    )

    handled = crear._redirect_expired_session(
        context,
        SessionExpiredError(),
        routes.append,
    )

    assert handled is True
    assert services.auth_tokens.access_token is None
    assert services.auth_tokens._refresh_token is None
    assert session_updates == [None]
    assert routes == [RoutePath.LOGIN]


def test_forbidden_response_preserves_the_current_session():
    services = build_demo_services()
    services.auth_tokens.replace("current-access", "current-refresh")
    session_updates = []
    routes = []
    context = AppContextValue(
        services=services,
        session=Session("directivo", is_admin=False, is_demo=False),
        set_session=session_updates.append,
    )

    handled = crear._redirect_expired_session(
        context,
        AuthorizationError(),
        routes.append,
    )

    assert handled is False
    assert services.auth_tokens.has_tokens is True
    assert session_updates == []
    assert routes == []


def test_empty_failed_subject_response_has_a_neutral_message():
    message = crear._failed_subjects_empty_message(0)

    assert message == "El alumno no tiene materias reprobadas registradas."


def test_non_eligible_failed_subjects_keep_the_period_rule_message():
    message = crear._failed_subjects_empty_message(2)

    assert message == "No hay materias que cumplan la regla 19 ≤ diferencia < 29."
