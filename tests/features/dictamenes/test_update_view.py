import asyncio
from datetime import date
from pathlib import Path
from types import SimpleNamespace

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
from esiqie_dictamenes.features.dictamenes.models import (
    Dictamen,
    DictamenPage,
    GeneratedDocument,
    PdfRequest,
)
from esiqie_dictamenes.features.dictamenes.pdf import format_session_date
from esiqie_dictamenes.features.dictamenes.views import buscar, modificar
from tests.helpers import authenticated_store, authenticated_user, build_test_services


def _utf8(value: bytes) -> str:
    return value.decode("utf-8")


_DICTAMINACION = _utf8(b"dictaminaci\xc3\xb3n")
_SESION = _utf8(b"sesi\xc3\xb3n")
_ACCION = _utf8(b"acci\xc3\xb3n")


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
        authenticated_user(is_admin=True),
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
        authenticated_user(is_admin=True),
        selected_keys=frozenset(),
        busy=True,
        on_selection=lambda _key, _selected: None,
    )

    row = table_row.controls[0].rows[0]
    assert row.disabled is True
    assert row.on_select_change is None


def test_normal_user_results_are_read_only_without_selection_callbacks():
    calls = []
    table_row = buscar._build_results_table(
        (_record(),),
        authenticated_user(is_admin=False),
        selected_keys=frozenset((_record().clave,)),
        busy=False,
        on_selection=lambda key, selected: calls.append((key, selected)),
    )
    table = table_row.controls[0]
    row = table.rows[0]

    assert table.show_checkbox_column is False
    assert row.selected is False
    assert row.on_select_change is None
    assert calls == []


def test_admin_action_guard_runs_before_synchronous_state_change():
    called = []

    with pytest.raises(AuthorizationError):
        buscar._run_admin_action(
            authenticated_store(is_admin=False).require_admin,
            lambda: called.append(True),
        )

    assert called == []


def test_admin_action_guard_allows_synchronous_state_change_once():
    called = []

    buscar._run_admin_action(
        authenticated_store(is_admin=True).require_admin,
        lambda: called.append(True),
    )

    assert called == [True]


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


def test_edit_form_captures_director_and_session_date_inputs():
    form = modificar._build_edit_form(
        record=_record(),
        value="DICTAMEN ORIGINAL",
        director="Dra. Directora",
        fecha_sesion=date(2026, 8, 30),
        busy=False,
        on_value=lambda _event: None,
        on_director=lambda _event: None,
        on_date=lambda: None,
        on_save=lambda: None,
        on_cancel=lambda: None,
    )
    fields = [
        control
        for control in _descendants(form)
        if isinstance(control, ft.TextField)
    ]

    assert [field.label for field in fields] == [
        "Nombre del director",
        f"Fecha de {_SESION}",
        _utf8(b"Dictaminaci\xc3\xb3n"),
    ]
    assert [field.value for field in fields] == [
        "Dra. Directora",
        format_session_date(date(2026, 8, 30)),
        "DICTAMEN ORIGINAL",
    ]
    assert fields[1].read_only is True


def test_edit_form_explains_that_director_and_session_date_are_pdf_only():
    form = modificar._build_edit_form(
        record=_record(),
        value="DICTAMEN ORIGINAL",
        director="Dra. Directora",
        fecha_sesion=date(2026, 8, 30),
        busy=False,
        on_value=lambda _event: None,
        on_director=lambda _event: None,
        on_date=lambda: None,
        on_save=lambda: None,
        on_cancel=lambda: None,
    )

    texts = [control.value for control in _descendants(form) if isinstance(control, ft.Text)]

    assert (
        f"Solo la {_DICTAMINACION} modifica el registro; "
        "director y fecha se usan para el PDF."
    ) in texts


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
                require_admin=authenticated_store().require_admin,
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
            require_admin=authenticated_store().require_admin,
        )
    )

    assert changed is False
    assert committed == []


def test_hidden_update_delegator_rejects_normal_user_before_controller_or_commit():
    calls = []
    committed = []

    class Controller:
        async def update_dictaminacion(self, record, value):
            calls.append((record, value))
            return record

    with pytest.raises(AuthorizationError):
        asyncio.run(
            buscar._load_update(
                Controller(),
                _record(),
                "NUEVO CONTENIDO",
                committed.append,
                require_admin=authenticated_store(
                    is_admin=False
                ).require_admin,
            )
        )

    assert calls == []
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


class _UpdateSelector:
    def __init__(self, destination):
        self.destination = destination
        self.calls = []

    async def select(self, record):
        self.calls.append(record)
        return self.destination


class _UpdateController:
    def __init__(self, updated=None, *, update_error=None, generate_error=None):
        self.updated = updated
        self.update_error = update_error
        self.generate_error = generate_error
        self.events = []
        self.update_calls = []
        self.prepare_calls = []
        self.generate_calls = []

    async def update_dictaminacion(self, current, value):
        self.events.append("put")
        self.update_calls.append((current, value))
        if self.update_error:
            raise self.update_error
        return self.updated

    def prepare_updated_pdf_request(self, dictamen, *, director, fecha_sesion):
        self.events.append("prepare")
        self.prepare_calls.append((dictamen, director, fecha_sesion))
        return PdfRequest(
            dictamen=dictamen,
            director=director,
            fecha_sesion=fecha_sesion,
            materias=(),
        )

    async def generate_pdf(self, request):
        self.events.append("generate")
        self.generate_calls.append(request)
        if self.generate_error:
            raise self.generate_error
        return GeneratedDocument("updated.pdf", b"%PDF", False)


class _UpdateStore:
    def __init__(self, *, validate_error=None, save_error=None):
        self.validate_error = validate_error
        self.save_error = save_error
        self.events = []
        self.validate_calls = []
        self.save_calls = []

    def validate_destination(self, destination):
        self.events.append("validate")
        self.validate_calls.append(destination)
        if self.validate_error:
            raise self.validate_error
        return Path(destination)

    async def save(self, destination, content):
        self.events.append("save")
        self.save_calls.append((destination, content))
        if self.save_error:
            raise self.save_error
        return destination


def _update_services(controller, store):
    return SimpleNamespace(
        auth_session=authenticated_store(),
        dictamen_controller=controller,
        document_store=store,
    )


def _update_workflow_kwargs(controller, store, **overrides):
    values = {
        "page": SimpleNamespace(web=False, platform=ft.PagePlatform.WINDOWS),
        "selector": _UpdateSelector("C:/tmp/actualizado.pdf"),
        "services": _update_services(controller, store),
        "current": _record(),
        "dictaminacion": "DICTAMEN ACTUALIZADO",
        "director": "Dra. Directora",
        "fecha_sesion": date(2026, 8, 30),
        "commit": lambda _updated: None,
    }
    values.update(overrides)
    return values


async def _update_pdf_workflow_with(controller, store, **overrides):
    return await buscar._update_pdf_workflow(
        **_update_workflow_kwargs(controller, store, **overrides)
    )


def test_update_pdf_workflow_orders_stages_and_uses_final_backend_identity():
    current = _record()
    updated = _record(text="DICTAMEN ACTUALIZADO")
    controller = _UpdateController(updated)
    store = _UpdateStore()
    events = []
    selector = _UpdateSelector("C:/tmp/actualizado.pdf")
    kwargs = _update_workflow_kwargs(
        controller,
        store,
        current=current,
        selector=selector,
        commit=lambda value: events.append(("commit", value)),
    )

    result = asyncio.run(buscar._update_pdf_workflow(**kwargs))

    assert result.updated is updated
    assert result.pdf_saved is True
    assert events == [("commit", updated)]
    assert controller.events == ["put", "prepare", "generate"]
    assert store.events == ["validate", "save"]
    assert selector.calls == [current]
    assert controller.update_calls == [(current, "DICTAMEN ACTUALIZADO")]
    request = controller.generate_calls[0]
    assert request.dictamen is updated
    assert request.director == "Dra. Directora"
    assert request.fecha_sesion == date(2026, 8, 30)
    assert request.materias == ()


def test_update_pdf_workflow_validates_destination_before_put():
    controller = _UpdateController(_record(text="DICTAMEN ACTUALIZADO"))
    store = _UpdateStore(validate_error=ValueError("invalid destination"))

    with pytest.raises(ValueError, match="invalid destination"):
        asyncio.run(_update_pdf_workflow_with(controller, store))

    assert controller.update_calls == []
    assert controller.generate_calls == []
    assert store.save_calls == []


@pytest.mark.parametrize(
    ("field", "value", "expected_message"),
    [
        ("dictaminacion", "  ", f"La {_DICTAMINACION} es obligatoria."),
        ("director", "  ", "El director es obligatorio."),
        (
            "fecha_sesion",
            None,
            f"Selecciona la fecha de {_SESION} en el calendario.",
        ),
    ],
)
def test_update_pdf_workflow_rejects_invalid_input_before_selector(
    field,
    value,
    expected_message,
):
    controller = _UpdateController(_record(text="DICTAMEN ACTUALIZADO"))
    store = _UpdateStore()
    selector = _UpdateSelector("C:/tmp/actualizado.pdf")
    kwargs = _update_workflow_kwargs(controller, store, selector=selector)
    kwargs[field] = value

    with pytest.raises(ValueError) as excinfo:
        asyncio.run(buscar._update_pdf_workflow(**kwargs))

    assert str(excinfo.value) == expected_message
    assert selector.calls == []
    assert controller.update_calls == []


def test_update_pdf_workflow_unchanged_dictaminacion_is_a_neutral_no_op():
    controller = _UpdateController(_record(text="DICTAMEN ACTUALIZADO"))
    store = _UpdateStore()
    selector = _UpdateSelector("C:/tmp/actualizado.pdf")

    result = asyncio.run(
        _update_pdf_workflow_with(
            controller,
            store,
            selector=selector,
            dictaminacion="  DICTAMEN ORIGINAL  ",
        )
    )

    assert result.no_op is True
    assert result.cancelled is False
    assert result.pdf_saved is False
    assert result.message == "No hay cambios por guardar."
    assert selector.calls == []
    assert controller.update_calls == []
    assert controller.generate_calls == []
    assert store.save_calls == []


def test_update_pdf_workflow_cancel_has_no_put_or_output():
    controller = _UpdateController(_record(text="DICTAMEN ACTUALIZADO"))
    store = _UpdateStore()
    selector = _UpdateSelector(None)

    result = asyncio.run(
        _update_pdf_workflow_with(controller, store, selector=selector)
    )

    assert result.cancelled is True
    assert controller.update_calls == []
    assert controller.generate_calls == []
    assert store.save_calls == []


@pytest.mark.parametrize(
    "page",
    [
        SimpleNamespace(web=True, platform=ft.PagePlatform.WINDOWS),
        SimpleNamespace(web=False, platform=ft.PagePlatform.ANDROID),
        SimpleNamespace(web=False, platform=ft.PagePlatform.IOS),
    ],
)
def test_update_pdf_workflow_blocks_web_mobile_before_selector(page):
    controller = _UpdateController(_record(text="DICTAMEN ACTUALIZADO"))
    store = _UpdateStore()
    selector = _UpdateSelector("C:/tmp/actualizado.pdf")

    with pytest.raises(ValueError):
        asyncio.run(
            _update_pdf_workflow_with(
                controller,
                store,
                page=page,
                selector=selector,
            )
        )

    assert selector.calls == []
    assert controller.update_calls == []


@pytest.mark.parametrize("stage", ["generate", "save"])
def test_update_pdf_workflow_output_failure_keeps_put_result_without_replay(stage):
    current = _record()
    updated = _record(text="DICTAMEN ACTUALIZADO")
    controller = _UpdateController(
        updated,
        generate_error=RuntimeError("render") if stage == "generate" else None,
    )
    store = _UpdateStore(
        save_error=RuntimeError("disk") if stage == "save" else None,
    )
    committed = []

    result = asyncio.run(
        _update_pdf_workflow_with(controller, store, commit=committed.append)
    )

    assert result.updated is updated
    assert result.pdf_saved is False
    assert updated.clave in result.message
    assert controller.update_calls == [(current, "DICTAMEN ACTUALIZADO")]
    assert committed == [updated]
    assert len(controller.generate_calls) == 1
    assert len(store.save_calls) == (0 if stage == "generate" else 1)


def test_update_pdf_workflow_treats_commit_failure_after_put_as_partial_success():
    """A local reconciliation failure must not disguise a completed PUT."""
    current = _record()
    updated = _record(text="DICTAMEN ACTUALIZADO")
    controller = _UpdateController(updated)
    store = _UpdateStore()

    def failing_commit(_updated):
        raise NotFoundError()

    result = asyncio.run(
        _update_pdf_workflow_with(controller, store, commit=failing_commit)
    )

    assert result.updated is updated
    assert result.pdf_saved is False
    assert updated.clave in result.message
    assert "ya no est" not in result.message
    assert controller.update_calls == [(current, "DICTAMEN ACTUALIZADO")]
    assert controller.generate_calls == []
    assert store.save_calls == []


def test_update_pdf_workflow_records_the_exact_stage_order():
    current = _record()
    updated = _record(text="DICTAMEN ACTUALIZADO")
    events = []

    class Selector(_UpdateSelector):
        async def select(self, record):
            events.append("selector")
            return await super().select(record)

    class Controller(_UpdateController):
        async def update_dictaminacion(self, current, value):
            events.append("put")
            return await super().update_dictaminacion(current, value)

        def prepare_updated_pdf_request(
            self, dictamen, *, director, fecha_sesion
        ):
            events.append("prepare")
            return super().prepare_updated_pdf_request(
                dictamen,
                director=director,
                fecha_sesion=fecha_sesion,
            )

        async def generate_pdf(self, request):
            events.append("generate")
            return await super().generate_pdf(request)

    class Store(_UpdateStore):
        def validate_destination(self, destination):
            events.append("validate")
            return super().validate_destination(destination)

        async def save(self, destination, content):
            events.append("save")
            return await super().save(destination, content)

    controller = Controller(updated)
    store = Store()

    asyncio.run(
        _update_pdf_workflow_with(
            controller,
            store,
            current=current,
            selector=Selector("C:/tmp/actualizado.pdf"),
            commit=lambda value: events.append(("commit", value)),
        )
    )

    assert events == [
        "selector",
        "validate",
        "put",
        ("commit", updated),
        "prepare",
        "generate",
        "save",
    ]


def test_update_pdf_failure_message_uses_safe_copy_and_selected_destination():
    message = buscar.post_update_pdf_failure_message(
        "CSE-0001-26",
        Path("C:/tmp/actualizado.pdf"),
    )

    assert "Dictamen actualizado correctamente. Clave: CSE-0001-26." in message
    assert (
        "El PDF no se pudo guardar; verifica el dictamen antes de intentar "
        f"cualquier otra {_ACCION}."
    ) in message
    assert "Ruta seleccionada: C:\\tmp\\actualizado.pdf." in message


def test_update_result_consumer_keeps_no_op_feedback_neutral():
    messages = []
    errors = []

    buscar._consume_update_pdf_result(
        buscar.UpdatePdfResult(
            updated=None,
            no_op=True,
            message="No hay cambios por guardar.",
        ),
        messages.append,
        errors.append,
    )

    assert messages == ["No hay cambios por guardar."]
    assert errors == [False]


def test_update_touched_files_do_not_contain_mojibake_markers():
    repo_root = Path(__file__).resolve().parents[3]
    touched_files = (
        repo_root / "src/esiqie_dictamenes/features/dictamenes/views/buscar.py",
        repo_root / "src/esiqie_dictamenes/features/dictamenes/views/pdf_output.py",
        repo_root / "NOTES.md",
    )

    for path in touched_files:
        content = path.read_text(encoding="utf-8")
        assert "Ã" not in content
        assert "Â" not in content
        assert "ƒ" not in content
