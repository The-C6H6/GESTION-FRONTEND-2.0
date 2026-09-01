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
from esiqie_dictamenes.features.alumnos.views.reprobados import (
    eligible_subjects_table,
)
from esiqie_dictamenes.features.alumnos.models import AlumnoDictaminable
from esiqie_dictamenes.features.dictamenes.controller import CreatedDictamen
from esiqie_dictamenes.features.dictamenes.models import (
    Dictamen,
    GeneratedDocument,
    MateriaElegible,
    PdfRequest,
)
from esiqie_dictamenes.features.dictamenes.pdf import build_pdf_filename
from esiqie_dictamenes.features.dictamenes.views import crear
from tests.helpers import authenticated_user, build_test_services


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
        materias=(MateriaElegible("Cálculo", 20252, 19, 2, "SI"),),
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


def test_normal_user_gets_read_only_candidate_copy():
    assert crear._page_copy(authenticated_user(is_admin=False)) == (
        "Consultar alumnos",
        "Consulta alumnos inscritos o con materias reprobadas.",
    )


def test_administrator_keeps_ruling_creation_copy():
    assert crear._page_copy(authenticated_user(is_admin=True)) == (
        "Nuevo dictamen",
        "Selecciona el tipo de alumno y captura los datos de la sesión.",
    )


def test_normal_user_keeps_query_controls_but_not_admin_controls():
    query_controls = (
        ft.Dropdown(key="dictamen-source"),
        ft.TextField(key="dictamen-student-query"),
        ft.TextField(key="dictamen-current-period"),
        ft.Button("Buscar", key="dictamen-student-search"),
        ft.Container(key="dictamen-student-result"),
    )
    admin_controls = (
        ft.TextField(key="dictamen-director"),
        ft.TextField(key="dictamen-session-date"),
        ft.TextField(key="dictamen-text"),
        ft.Button("Crear dictamen", key="dictamen-create"),
    )

    assert [control.key for control in query_controls] == [
        "dictamen-source",
        "dictamen-student-query",
        "dictamen-current-period",
        "dictamen-student-search",
        "dictamen-student-result",
    ]
    assert crear._admin_controls(
        authenticated_user(is_admin=False), admin_controls
    ) == ()
    assert crear._admin_controls(
        authenticated_user(is_admin=True), admin_controls
    ) == admin_controls


def test_hidden_create_delegator_rejects_normal_user_before_controller_call():
    auth_session = build_test_services(is_admin=False).auth_session
    calls = []

    class Controller:
        async def create(self, **kwargs):
            calls.append(kwargs)

    services = SimpleNamespace(
        auth_session=auth_session,
        dictamen_controller=Controller(),
    )

    with pytest.raises(AuthorizationError):
        asyncio.run(crear._create_dictamen(services, alumno=object()))

    assert calls == []


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

    handled = crear._redirect_expired_session(
        context,
        SessionExpiredError(),
        routes.append,
    )

    assert handled is True
    assert services.auth_session.current is None
    assert session_updates == [None]
    assert routes == [RoutePath.LOGIN]


def test_forbidden_response_preserves_the_current_session():
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

    handled = crear._redirect_expired_session(
        context,
        AuthorizationError(),
        routes.append,
    )

    assert handled is False
    assert services.auth_session.current is session
    assert session_updates == []
    assert routes == []


def test_empty_eligible_subjects_table_renders_no_message():
    section = eligible_subjects_table(())

    assert isinstance(section, ft.Container)
    assert section.content is None


def test_non_eligible_failed_subjects_show_count_and_unavailable_message():
    section = crear._build_failed_subjects_section((), total_reprobadas=3)

    assert isinstance(section, ft.Column)
    assert [control.value for control in section.controls] == [
        "Materias reprobadas: 3",
        (
            "El alumno no puede dictaminarse por que no tiene materias "
            "que se puedan dictaminar"
        ),
    ]


@pytest.mark.parametrize(
    ("source", "alumno", "materias", "total_reprobadas", "expected"),
    [
        ("reprobado", object(), (), 3, True),
        ("reprobado", object(), (MateriaElegible("Cálculo", 20252, 19, 2, "SI"),), 3, False),
        ("inscrito", object(), (), 0, False),
        ("reprobado", None, (), 0, False),
    ],
)
def test_ruling_is_unavailable_only_for_selected_failed_students_without_eligible_subjects(
    source,
    alumno,
    materias,
    total_reprobadas,
    expected,
):
    assert (
        crear._is_ruling_unavailable(
            source,
            alumno,
            materias,
            total_reprobadas,
        )
        is expected
    )


def test_create_button_is_disabled_when_the_ruling_is_unavailable():
    button = crear._build_create_button(
        search_busy=False,
        create_busy=False,
        on_click=lambda: None,
        ruling_unavailable=True,
    )

    assert button.disabled is True


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


@pytest.mark.parametrize(
    ("web", "platform", "supported"),
    [
        (True, ft.PagePlatform.WINDOWS, False),
        (False, ft.PagePlatform.ANDROID, False),
        (False, ft.PagePlatform.IOS, False),
        (False, ft.PagePlatform.WINDOWS, True),
        (False, ft.PagePlatform.MACOS, True),
        (False, ft.PagePlatform.LINUX, True),
    ],
)
def test_pdf_output_platform_support_is_desktop_only(web, platform, supported):
    from esiqie_dictamenes.features.dictamenes.views.pdf_output import (
        platform_supports_pdf_output,
    )

    assert platform_supports_pdf_output(web=web, platform=platform) is supported


def test_pdf_selector_uses_canonical_filename_and_does_not_send_bytes():
    from esiqie_dictamenes.features.dictamenes.views.pdf_output import (
        FletPdfDestinationSelector,
    )

    dictamen = Dictamen(
        clave="",
        boleta="2021320863",
        alumno="Ana Alumna",
        fecha=date(2026, 8, 30),
        anio=2026,
        dictaminacion="Aceptada",
    )

    class Picker:
        def __init__(self):
            self.calls = []

        async def save_file(self, **kwargs):
            self.calls.append(kwargs)
            return "C:/tmp/resultado.pdf"

    picker = Picker()
    selected = asyncio.run(FletPdfDestinationSelector(picker).select(dictamen))

    assert selected == "C:/tmp/resultado.pdf"
    assert picker.calls == [
        {
            "file_name": build_pdf_filename(dictamen),
            "file_type": ft.FilePickerFileType.CUSTOM,
            "allowed_extensions": ["pdf"],
        }
    ]


def _created_result(*, clave="CSE-0001-26"):
    dictamen = Dictamen(
        clave=clave,
        boleta="2021320863",
        alumno="Ana Alumna",
        fecha=date(2026, 8, 30),
        anio=2026,
        dictaminacion="Aceptada",
    )
    request = PdfRequest(
        dictamen=dictamen,
        director="Directora",
        fecha_sesion=date(2026, 8, 30),
        materias=(MateriaElegible("Cálculo", 20252, 19, 2, "SI"),),
    )
    return CreatedDictamen(dictamen, object(), request)


class _WorkflowController:
    def __init__(self, result=None, create_error=None, generation_error=None):
        self.result = result or _created_result()
        self.create_error = create_error
        self.generation_error = generation_error
        self.create_calls = []
        self.generate_calls = []

    async def create(self, **kwargs):
        self.create_calls.append(kwargs)
        if self.create_error:
            raise self.create_error
        return self.result

    async def generate_pdf(self, request):
        self.generate_calls.append(request)
        if self.generation_error:
            raise self.generation_error
        return GeneratedDocument("generated.pdf", b"pdf", False)


class _WorkflowSelector:
    def __init__(self, path):
        self.path = path
        self.calls = []

    async def select(self, dictamen):
        self.calls.append(dictamen)
        return self.path


class _WorkflowStore:
    def __init__(self, path="C:/tmp/resultado.pdf", validate_error=None, save_error=None):
        self.path = path
        self.validate_error = validate_error
        self.save_error = save_error
        self.validate_calls = []
        self.save_calls = []

    def validate_destination(self, path):
        self.validate_calls.append(path)
        if self.validate_error:
            raise self.validate_error
        return self.path

    async def save(self, path, content):
        self.save_calls.append((path, content))
        if self.save_error:
            raise self.save_error
        return self.path


def _workflow_services(controller, store):
    class Auth:
        def __init__(self):
            self.calls = 0

        def require_admin(self):
            self.calls += 1

    services = SimpleNamespace(
        auth_session=Auth(),
        dictamen_controller=controller,
        document_store=store,
    )
    return services


def _workflow_kwargs(**overrides):
    values = {
        "page": SimpleNamespace(web=False, platform=ft.PagePlatform.WINDOWS),
        "selector": _WorkflowSelector("C:/tmp/resultado.pdf"),
        "services": None,
        "alumno": AlumnoDictaminable("2021320863", "Ana Alumna", "IQI"),
        "dictaminacion": "Aceptada",
        "director": "Directora",
        "materias": (MateriaElegible("Cálculo", 20252, 19, 2, "SI"),),
        "reference": date(2026, 8, 30),
        "fecha_sesion": date(2026, 8, 30),
    }
    values.update(overrides)
    return values


def test_create_pdf_workflow_orders_selector_create_generate_and_save():
    controller = _WorkflowController()
    store = _WorkflowStore(path="C:/tmp/resultado_2.pdf")
    services = _workflow_services(controller, store)
    kwargs = _workflow_kwargs(services=services)

    result = asyncio.run(crear._create_pdf_workflow(**kwargs))

    assert result.saved_path == "C:/tmp/resultado_2.pdf"
    assert len(kwargs["selector"].calls) == 1
    assert len(controller.create_calls) == 1
    assert len(controller.generate_calls) == 1
    assert len(store.save_calls) == 1
    assert controller.create_calls[0]["materias"] == kwargs["materias"]


def test_create_pdf_workflow_records_the_exact_stage_order():
    events = []

    class Selector(_WorkflowSelector):
        async def select(self, dictamen):
            events.append("selector")
            return await super().select(dictamen)

    class Controller(_WorkflowController):
        async def create(self, **kwargs):
            events.append("create")
            return await super().create(**kwargs)

        async def generate_pdf(self, request):
            events.append("generate")
            return await super().generate_pdf(request)

    class Store(_WorkflowStore):
        def validate_destination(self, path):
            events.append("validate")
            return super().validate_destination(path)

        async def save(self, path, content):
            events.append("save")
            return await super().save(path, content)

    controller = Controller()
    store = Store()
    services = _workflow_services(controller, store)

    asyncio.run(
        _create_workflow_with(
            services,
            controller,
            store,
            selector=Selector("C:/tmp/resultado.pdf"),
        )
    )

    assert events == ["selector", "validate", "create", "generate", "save"]


def test_create_pdf_workflow_cancellation_has_no_mutation_or_output():
    controller = _WorkflowController()
    store = _WorkflowStore()
    services = _workflow_services(controller, store)
    kwargs = _workflow_kwargs(
        services=services,
        selector=_WorkflowSelector(None),
    )

    result = asyncio.run(crear._create_pdf_workflow(**kwargs))

    assert result.cancelled is True
    assert controller.create_calls == []
    assert controller.generate_calls == []
    assert store.save_calls == []


def test_create_pdf_workflow_invalid_destination_has_no_mutation():
    controller = _WorkflowController()
    store = _WorkflowStore(validate_error=ValueError("invalid"))
    services = _workflow_services(controller, store)

    with pytest.raises(ValueError, match="invalid"):
        asyncio.run(_create_workflow_with(services, controller, store))

    assert controller.create_calls == []
    assert controller.generate_calls == []
    assert store.save_calls == []


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("alumno", None, "Primero busca y selecciona un alumno."),
        ("dictaminacion", "   ", "La dictaminación es obligatoria."),
        ("director", "   ", "El director es obligatorio."),
        (
            "fecha_sesion",
            "30 DE AGOSTO",
            "Selecciona la fecha de sesión en el calendario.",
        ),
        ("reference", "2026-08-30", "La fecha del dictamen no es válida."),
    ],
)
def test_create_pdf_workflow_rejects_invalid_input_before_any_output_stage(
    field,
    value,
    message,
):
    """Keep all local CREATE validation ahead of selection and mutation."""
    controller = _WorkflowController()
    store = _WorkflowStore()
    selector = _WorkflowSelector("C:/tmp/resultado.pdf")
    services = _workflow_services(controller, store)

    with pytest.raises(ValueError, match=message):
        asyncio.run(
            _create_workflow_with(
                services,
                controller,
                store,
                selector=selector,
                **{field: value},
            )
        )

    assert selector.calls == []
    assert store.validate_calls == []
    assert controller.create_calls == []
    assert controller.generate_calls == []
    assert store.save_calls == []


async def _create_workflow_with(services, controller, store, **overrides):
    kwargs = _workflow_kwargs(services=services, **overrides)
    return await crear._create_pdf_workflow(**kwargs)


@pytest.mark.parametrize(
    "platform", [ft.PagePlatform.ANDROID, ft.PagePlatform.IOS]
)
def test_create_pdf_workflow_blocks_web_mobile_before_selector_and_mutation(platform):
    controller = _WorkflowController()
    store = _WorkflowStore()
    selector = _WorkflowSelector("C:/tmp/resultado.pdf")
    services = _workflow_services(controller, store)

    with pytest.raises(ValueError):
        asyncio.run(
            _create_workflow_with(
                services,
                controller,
                store,
                page=SimpleNamespace(web=False, platform=platform),
                selector=selector,
            )
        )

    assert selector.calls == []
    assert controller.create_calls == []


def test_create_pdf_workflow_blocks_web_before_selector_and_mutation():
    controller = _WorkflowController()
    store = _WorkflowStore()
    selector = _WorkflowSelector("C:/tmp/resultado.pdf")
    services = _workflow_services(controller, store)

    with pytest.raises(ValueError):
        asyncio.run(
            _create_workflow_with(
                services,
                controller,
                store,
                page=SimpleNamespace(web=True, platform=ft.PagePlatform.WINDOWS),
                selector=selector,
            )
        )

    assert selector.calls == []
    assert controller.create_calls == []


def test_create_pdf_workflow_backend_failure_does_not_generate_or_save():
    controller = _WorkflowController(create_error=RuntimeError("backend"))
    store = _WorkflowStore()
    services = _workflow_services(controller, store)

    with pytest.raises(RuntimeError, match="backend"):
        asyncio.run(_create_workflow_with(services, controller, store))

    assert controller.generate_calls == []
    assert store.save_calls == []


def test_create_pdf_workflow_generation_failure_retains_created_key_without_retry():
    controller = _WorkflowController(generation_error=RuntimeError("render"))
    store = _WorkflowStore()
    services = _workflow_services(controller, store)
    invalidated = []

    result = asyncio.run(
        _create_workflow_with(
            services,
            controller,
            store,
            on_post_mutation_failure=invalidated.append,
        )
    )

    assert result.dictamen.clave == "CSE-0001-26"
    assert result.pdf_saved is False
    assert result.message.find("CSE-0001-26") >= 0
    assert len(controller.create_calls) == 1
    assert len(controller.generate_calls) == 1
    assert store.save_calls == []
    assert invalidated == [result.dictamen]


def test_create_pdf_workflow_save_failure_retains_created_key_without_retry():
    controller = _WorkflowController()
    store = _WorkflowStore(save_error=RuntimeError("disk"))
    services = _workflow_services(controller, store)
    invalidated = []

    result = asyncio.run(
        _create_workflow_with(
            services,
            controller,
            store,
            on_post_mutation_failure=invalidated.append,
        )
    )

    assert result.dictamen.clave == "CSE-0001-26"
    assert result.pdf_saved is False
    assert "CSE-0001-26" in result.message
    assert len(controller.create_calls) == 1
    assert len(controller.generate_calls) == 1
    assert len(store.save_calls) == 1
    assert invalidated == [result.dictamen]


def test_create_result_consumer_keeps_cancellation_neutral():
    from esiqie_dictamenes.features.dictamenes.views.pdf_output import CreatePdfResult

    messages = []
    errors = []

    crear._consume_create_pdf_result(
        CreatePdfResult(dictamen=None, cancelled=True),
        messages.append,
        errors.append,
    )

    assert messages == []
    assert errors == []
