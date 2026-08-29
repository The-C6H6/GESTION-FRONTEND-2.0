import asyncio
from datetime import date

import pytest

from esiqie_dictamenes.core.context import AppContextValue
from esiqie_dictamenes.core.errors import SessionExpiredError, ValidationError
from esiqie_dictamenes.core.routes import RoutePath
from esiqie_dictamenes.features.dictamenes.models import (
    Dictamen,
    DictamenFilter,
    DictamenPage,
)
from esiqie_dictamenes.features.dictamenes.views import buscar
from tests.helpers import authenticated_user, build_test_services


@pytest.mark.parametrize(
    ("criterion", "query", "expected"),
    [
        ("boleta", " 2022630000 ", DictamenFilter(boleta="2022630000")),
        ("anio", " 2026 ", DictamenFilter(anio=2026)),
    ],
)
def test_search_filter_normalizes_only_supported_criteria(
    criterion,
    query,
    expected,
):
    assert buscar._build_filter(criterion, query) == expected


@pytest.mark.parametrize(
    ("criterion", "query"),
    [("boleta", " "), ("anio", "20XX"), ("clave", "CSE-0001-26")],
)
def test_search_filter_rejects_blank_invalid_year_and_unknown_criterion(
    criterion,
    query,
):
    with pytest.raises(ValidationError):
        buscar._build_filter(criterion, query)


def test_pagination_copy_uses_server_total_and_current_page_range():
    page = DictamenPage(total=347, skip=100, limit=100, items=tuple(range(100)))

    labels = buscar._pagination_labels(page, current_page=2)

    assert labels == (
        "P\u00e1gina 2 de 4",
        "Mostrando 101\u2013200 de 347 dict\u00e1menes",
    )


def test_empty_page_uses_the_neutral_no_results_message():
    page = DictamenPage(total=0, skip=0, limit=100, items=())

    assert buscar._search_success_message(page) == (
        "No se encontraron dict\u00e1menes"
    )


def test_request_gate_rejects_a_second_concurrent_search():
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

    calls, busy_states, first_result, second_result = asyncio.run(scenario())

    assert calls == 1
    assert busy_states == [True, False]
    assert first_result is True
    assert second_result is False


def test_failed_page_request_does_not_commit_new_filter_page_or_results():
    committed = {
        "filter": DictamenFilter(anio=2025),
        "page": 2,
        "result": object(),
    }

    class FailingController:
        async def search_page(self, filters, *, page):
            raise RuntimeError("network failed")

    async def scenario():
        await buscar._load_page(
            FailingController(),
            DictamenFilter(anio=2026),
            1,
            lambda filters, page, result: committed.update(
                filter=filters,
                page=page,
                result=result,
            ),
        )

    with pytest.raises(RuntimeError, match="network failed"):
        asyncio.run(scenario())

    assert committed["filter"] == DictamenFilter(anio=2025)
    assert committed["page"] == 2


def test_expired_search_session_clears_tokens_and_navigates_to_login():
    services = build_test_services()
    session = services.auth_session.current
    assert session is not None
    session_updates = []
    routes = []
    context = AppContextValue(
        services=services,
        session=session,
        set_session=session_updates.append,
    )

    message = buscar._search_error_message(
        context,
        SessionExpiredError(),
        routes.append,
    )

    assert message == ""
    assert services.auth_session.current is None
    assert session_updates == [None]
    assert routes == [RoutePath.LOGIN]


def test_search_controls_are_disabled_during_any_page_request():
    controls = buscar._build_search_controls(
        criterion="boleta",
        query="2022630000",
        busy=True,
        on_criterion=lambda _event: None,
        on_query=lambda _event: None,
        on_search=lambda: None,
    )

    assert all(control.disabled for control in controls.controls)


def test_modify_selection_action_is_disabled_during_a_page_request():
    record = Dictamen(
        clave="CSE-0001-26",
        boleta="2022630000",
        alumno="NOMBRE DEL ALUMNO",
        fecha=date(2026, 8, 26),
        anio=2026,
        dictaminacion="DICTAMINACIÃ“N",
    )

    actions = buscar._build_selection_actions(
        authenticated_user(is_admin=True),
        busy=True,
        has_results=True,
        editing=False,
        on_edit=lambda: None,
    )
    action = actions.controls[0]

    assert action.disabled is True
