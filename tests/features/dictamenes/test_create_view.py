import asyncio
from datetime import date, datetime
from types import SimpleNamespace

import flet as ft
import pytest

from esiqie_dictamenes.core.context import AppContextValue
from esiqie_dictamenes.core.errors import (
    ApiConnectionError,
    ApiTimeoutError,
    AuthorizationError,
    SessionExpiredError,
)
from esiqie_dictamenes.core.routes import RoutePath
from esiqie_dictamenes.core.services import build_demo_services
from esiqie_dictamenes.features.alumnos.views.reprobados import (
    eligible_subjects_table,
)
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


def test_student_search_delegates_the_selected_source_to_the_use_case():
    selected_student = SimpleNamespace(boleta="2024999999")
    candidate = SimpleNamespace(
        alumno=selected_student,
        materias=(MateriaElegible("Cálculo", 20252, 19),),
        total_reprobadas=1,
    )

    class DictamenControllerSpy:
        def __init__(self):
            self.calls = []

        async def find_student_candidate(self, source, query, period):
            self.calls.append((source, query, period))
            return candidate

    dictamen_controller = DictamenControllerSpy()
    services = SimpleNamespace(
        dictamen_controller=dictamen_controller,
    )

    result = asyncio.run(
        crear._find_student(services, "reprobado", "2024999999", "20271")
    )

    assert dictamen_controller.calls == [
        ("reprobado", "2024999999", "20271")
    ]
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
            crear._run_guarded_request(gate, busy_states.append, operation)
        )
        await started.wait()
        second_result = await crear._run_guarded_request(
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
            crear._run_guarded_request(gate, busy_states.append, failing_operation)
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


def test_empty_eligible_subjects_table_renders_no_message():
    section = eligible_subjects_table(())

    assert isinstance(section, ft.Container)
    assert section.content is None


def test_create_button_is_disabled_while_a_student_search_is_running():
    button = crear._build_create_button(
        search_busy=True,
        create_busy=False,
        on_click=lambda: None,
    )

    assert button.disabled is True


def test_create_button_is_disabled_while_the_post_is_running():
    button = crear._build_create_button(
        search_busy=False,
        create_busy=True,
        on_click=lambda: None,
    )

    assert button.disabled is True


def test_create_gate_allows_only_one_concurrent_post():
    async def scenario():
        gate = crear._RequestGate()
        started = asyncio.Event()
        release = asyncio.Event()
        busy_states = []
        posts = 0

        async def post():
            nonlocal posts
            posts += 1
            started.set()
            await release.wait()

        first = asyncio.create_task(
            crear._run_guarded_request(gate, busy_states.append, post)
        )
        await started.wait()
        second_result = await crear._run_guarded_request(
            gate,
            busy_states.append,
            post,
        )
        release.set()
        first_result = await first
        return posts, busy_states, first_result, second_result

    posts, busy_states, first_result, second_result = asyncio.run(scenario())

    assert posts == 1
    assert busy_states == [True, False]
    assert first_result is True
    assert second_result is False


@pytest.mark.parametrize("error", [ApiTimeoutError(), ApiConnectionError()])
def test_ambiguous_create_failure_warns_that_the_result_is_unconfirmed(error):
    message = crear._creation_error_message(error)

    assert message == (
        "No se pudo confirmar si el dictamen fue creado. "
        "Verifica antes de intentarlo nuevamente."
    )


def test_creation_success_message_exposes_the_backend_key():
    message = crear._creation_success_message("CSE-0001-26")

    assert message == "Dictamen creado correctamente. Clave: CSE-0001-26"


def test_changing_a_search_criterion_invalidates_the_selected_student():
    criterion_updates = []
    student_updates = []
    subject_updates = []
    total_updates = []

    crear._change_search_criterion(
        "2025320001",
        criterion_updates.append,
        student_updates.append,
        subject_updates.append,
        total_updates.append,
    )

    assert criterion_updates == ["2025320001"]
    assert student_updates == [None]
    assert subject_updates == [()]
    assert total_updates == [0]
