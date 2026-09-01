import asyncio
from datetime import date
from types import SimpleNamespace

import pytest

from esiqie_dictamenes.core.errors import (
    AuthorizationError,
    NotFoundError,
    UnexpectedResponseError,
    ValidationError,
)
from esiqie_dictamenes.features.dictamenes.controller import DictamenController
from esiqie_dictamenes.features.dictamenes.models import (
    Dictamen,
    DictamenFilter,
    DictamenPage,
    GeneratedDocument,
    MateriaReprobada,
    PdfRequest,
)
from esiqie_dictamenes.infrastructure.demo.alumno_repository import DemoAlumnoRepository
from esiqie_dictamenes.infrastructure.demo.dictamen_repository import DemoDictamenRepository
from tests.helpers import RecordingPdfGenerator, authenticated_store


def build_controller():
    store = authenticated_store()
    return DictamenController(
        DemoDictamenRepository(),
        DemoAlumnoRepository(),
        RecordingPdfGenerator(),
        require_admin=store.require_admin,
        search_repository=DemoDictamenRepository(),
    )


def test_controller_requires_an_explicit_search_repository():
    with pytest.raises(TypeError, match="search_repository"):
        DictamenController(
            DemoDictamenRepository(),
            DemoAlumnoRepository(),
            RecordingPdfGenerator(),
            require_admin=authenticated_store().require_admin,
        )


def test_reprobados_flow_includes_every_eligible_subject_automatically():
    controller = build_controller()

    result = asyncio.run(controller.find_eligible_reprobados("2024320678", "20271"))

    assert [(item.materia, item.diferencia) for item in result] == [
        ("Cálculo diferencial", 19),
        ("Termodinámica", 28),
    ]


def test_reprobados_flow_resolves_student_data_when_searching_by_name():
    controller = build_controller()

    result = asyncio.run(controller.find_reprobado_candidate("Ana", "20271"))

    assert result.alumno.boleta == "2024320678"
    assert [item.materia for item in result.materias] == [
        "Cálculo diferencial",
        "Termodinámica",
    ]


def test_enrolled_source_uses_only_the_enrolled_student_repository():
    alumno = asyncio.run(DemoAlumnoRepository().get_inscrito("2024320678"))

    class EnrolledRepository:
        async def get_inscrito(self, boleta):
            assert boleta == "2024320678"
            return alumno

    class RejectingReprobadoRepository:
        async def search_reprobados(self, boleta=None, nombre=None):
            raise AssertionError("The failed-subject repository must not be called.")

    controller = DictamenController(
        DemoDictamenRepository(),
        EnrolledRepository(),
        RecordingPdfGenerator(),
        require_admin=authenticated_store().require_admin,
        reprobado_repository=RejectingReprobadoRepository(),
        search_repository=DemoDictamenRepository(),
    )

    result = asyncio.run(
        controller.find_student_candidate("inscrito", "2024320678", "20271")
    )

    assert result.alumno.boleta == "2024320678"
    assert result.alumno.nombre == "Ana López Martínez"
    assert result.materias == ()


def test_failed_source_uses_only_reprobados_and_builds_its_own_student():
    class RejectingInscritoRepository:
        async def get_inscrito(self, boleta):
            raise AssertionError("The enrolled-student repository must not be called.")

    class RecordingReprobadoRepository:
        def __init__(self):
            self.boletas = []

        async def search_reprobados(self, boleta=None, nombre=None):
            self.boletas.append(boleta)
            return (
                SimpleNamespace(
                    materia="Cálculo diferencial",
                    periodo_reprobada=20252,
                    intentos_ordinario=2,
                    materia_inscrita="SI",
                    boleta=boleta,
                    nombre="Alumno solo reprobado",
                    carrera="Ingeniería Química Industrial",
                ),
            )

    reprobados = RecordingReprobadoRepository()
    controller = DictamenController(
        DemoDictamenRepository(),
        RejectingInscritoRepository(),
        RecordingPdfGenerator(),
        require_admin=authenticated_store().require_admin,
        reprobado_repository=reprobados,
        search_repository=DemoDictamenRepository(),
    )

    result = asyncio.run(
        controller.find_student_candidate("reprobado", "2024999999", "20271")
    )

    assert reprobados.boletas == ["2024999999"]
    assert result.alumno.boleta == "2024999999"
    assert result.alumno.nombre == "Alumno solo reprobado"
    assert result.alumno.carrera == "Ingeniería Química Industrial"
    assert not hasattr(result.alumno, "creditos_inscritos")
    assert result.total_reprobadas == 1
    assert [item.materia for item in result.materias] == ["Cálculo diferencial"]


def test_failed_source_reports_an_empty_page_without_falling_back_to_inscritos():
    class RejectingInscritoRepository:
        async def get_inscrito(self, boleta):
            raise AssertionError("An empty failed-subject page must not fall back.")

    class EmptyReprobadoRepository:
        async def search_reprobados(self, boleta=None, nombre=None):
            return ()

    controller = DictamenController(
        DemoDictamenRepository(),
        RejectingInscritoRepository(),
        RecordingPdfGenerator(),
        require_admin=authenticated_store().require_admin,
        reprobado_repository=EmptyReprobadoRepository(),
        search_repository=DemoDictamenRepository(),
    )

    with pytest.raises(
        NotFoundError,
        match="No se encontraron materias reprobadas para la boleta indicada",
    ):
        asyncio.run(
            controller.find_student_candidate("reprobado", "2024999999", "20271")
        )


def test_create_keeps_pdf_context_separate_without_generating_a_document():
    class RejectingPdfGenerator:
        async def generate(self, request):
            raise AssertionError("Creation must not generate a PDF.")

    controller = DictamenController(
        DemoDictamenRepository(),
        DemoAlumnoRepository(),
        RejectingPdfGenerator(),
        require_admin=authenticated_store().require_admin,
        search_repository=DemoDictamenRepository(),
    )
    alumno = asyncio.run(DemoAlumnoRepository().get_inscrito("2024320678"))

    result = asyncio.run(
        controller.create(
            alumno=alumno,
            dictaminacion="Artículo 56",
            director="Dr. Dirección Escolar",
            materias=(),
            reference=date(2026, 8, 24),
            fecha_sesion=date(2026, 12, 11),
        )
    )

    assert result.dictamen.boleta == "2024320678"
    assert result.dictamen.anio == 2026
    assert result.pdf_request.director == "Dr. Dirección Escolar"
    assert result.pdf_request.fecha_sesion == date(2026, 12, 11)
    assert result.api_payload.fecha == date(2026, 8, 24)
    assert not hasattr(result.api_payload, "director")
    assert not hasattr(result.api_payload, "fecha_sesion")
    assert not hasattr(result, "document")


def test_real_failed_subjects_remain_in_pdf_context_but_not_api_payload():
    controller = build_controller()
    candidate = asyncio.run(
        controller.find_student_candidate(
            "reprobado",
            "2024320678",
            "20271",
        )
    )

    result = asyncio.run(
        controller.create(
            alumno=candidate.alumno,
            dictaminacion="Artículo 56",
            director="Dr. Dirección Escolar",
            materias=candidate.materias,
            reference=date(2026, 8, 26),
            fecha_sesion=date(2026, 12, 11),
        )
    )

    assert [item.materia for item in result.pdf_request.materias] == [
        "Cálculo diferencial",
        "Termodinámica",
    ]
    assert not hasattr(result.api_payload, "materias")


def test_create_rejects_a_free_text_session_date():
    controller = build_controller()
    alumno = asyncio.run(DemoAlumnoRepository().get_inscrito("2024320678"))

    with pytest.raises(ValidationError, match="fecha de sesión"):
        asyncio.run(
            controller.create(
                alumno=alumno,
                dictaminacion="Artículo 56",
                director="Dr. Dirección Escolar",
                materias=(),
                reference=date(2026, 8, 24),
                fecha_sesion="11 DE DICIEMBRE",
            )
        )


def test_delete_rejects_an_empty_selection():
    class RejectingDeleteRepository:
        async def delete_many(self, claves):
            raise AssertionError("Empty selection must not reach the repository.")

    controller = DictamenController(
        DemoDictamenRepository(),
        DemoAlumnoRepository(),
        RecordingPdfGenerator(),
        require_admin=authenticated_store().require_admin,
        delete_repository=RejectingDeleteRepository(),
        search_repository=DemoDictamenRepository(),
    )

    with pytest.raises(ValidationError, match="Selecciona"):
        asyncio.run(controller.delete_dictamenes(()))


def test_delete_uses_unique_keys_from_selected_domain_entities():
    first = asyncio.run(DemoDictamenRepository().get("D-00132"))
    second = asyncio.run(DemoDictamenRepository().get("D-00081"))

    class DeleteRepository:
        def __init__(self):
            self.calls = []

        async def delete_many(self, claves):
            self.calls.append(tuple(claves))
            return len(claves)

    delete_repository = DeleteRepository()
    controller = DictamenController(
        DemoDictamenRepository(),
        DemoAlumnoRepository(),
        RecordingPdfGenerator(),
        require_admin=authenticated_store().require_admin,
        delete_repository=delete_repository,
        search_repository=DemoDictamenRepository(),
    )

    total = asyncio.run(
        controller.delete_dictamenes((first, first, second))
    )

    assert total == 2
    assert delete_repository.calls == [(first.clave, second.clave)]


def test_paginated_search_converts_page_number_to_skip_and_preserves_filter():
    expected = DictamenPage(
        total=347,
        skip=100,
        limit=100,
        items=(
            Dictamen(
                "CSE-0101-26",
                "2022630000",
                "NOMBRE DEL ALUMNO",
                date(2026, 8, 26),
                2026,
                "DICTAMINACIÃ“N",
            ),
        ),
    )

    class SearchRepository:
        def __init__(self):
            self.calls = []

        async def search_page(self, filters, *, skip, limit):
            self.calls.append((filters, skip, limit))
            return expected

    search_repository = SearchRepository()
    controller = DictamenController(
        DemoDictamenRepository(),
        DemoAlumnoRepository(),
        RecordingPdfGenerator(),
        require_admin=authenticated_store().require_admin,
        search_repository=search_repository,
    )

    result = asyncio.run(
        controller.search_page(DictamenFilter(anio=2026), page=2)
    )

    assert result is expected
    assert search_repository.calls == [(DictamenFilter(anio=2026), 100, 100)]


@pytest.mark.parametrize(
    ("filters", "page"),
    [
        (DictamenFilter(), 1),
        (DictamenFilter(boleta="2022630000", anio=2026), 1),
        (DictamenFilter(boleta="2022630000"), 0),
    ],
)
def test_paginated_search_rejects_invalid_filter_or_page(filters, page):
    controller = build_controller()

    with pytest.raises(ValidationError):
        asyncio.run(controller.search_page(filters, page=page))


def test_update_preserves_read_only_ruling_metadata():
    controller = build_controller()

    result = asyncio.run(controller.update("D-00132", "Causa actualizada"))

    assert result.clave == "D-00132"
    assert result.boleta == "2024320678"
    assert result.anio == 2025
    assert result.dictaminacion == "Causa actualizada"


def test_real_update_changes_only_dictaminacion_after_repository_success():
    current = asyncio.run(DemoDictamenRepository().get("D-00132"))

    class UpdateRepository:
        def __init__(self):
            self.calls = []

        async def update(self, clave, payload):
            self.calls.append((clave, payload))
            return Dictamen(
                current.clave,
                current.boleta,
                current.alumno,
                current.fecha,
                current.anio,
                payload.dictaminacion,
            )

    update_repository = UpdateRepository()
    controller = DictamenController(
        DemoDictamenRepository(),
        DemoAlumnoRepository(),
        RecordingPdfGenerator(),
        require_admin=authenticated_store().require_admin,
        update_repository=update_repository,
        search_repository=DemoDictamenRepository(),
    )

    result = asyncio.run(
        controller.update_dictaminacion(current, "  Nueva dictaminaciÃ³n  ")
    )

    assert len(update_repository.calls) == 1
    clave, payload = update_repository.calls[0]
    assert clave == current.clave
    assert payload.dictaminacion == "Nueva dictaminaciÃ³n"
    assert result.dictaminacion == "Nueva dictaminaciÃ³n"
    assert (
        result.clave,
        result.boleta,
        result.alumno,
        result.fecha,
        result.anio,
    ) == (
        current.clave,
        current.boleta,
        current.alumno,
        current.fecha,
        current.anio,
    )


@pytest.mark.parametrize("value", ["", "   ", None, 2026])
def test_real_update_rejects_empty_or_non_string_values_without_a_put(value):
    class RejectingUpdateRepository:
        async def update(self, clave, payload):
            raise AssertionError("Invalid input must not reach the repository.")

    controller = DictamenController(
        DemoDictamenRepository(),
        DemoAlumnoRepository(),
        RecordingPdfGenerator(),
        require_admin=authenticated_store().require_admin,
        update_repository=RejectingUpdateRepository(),
        search_repository=DemoDictamenRepository(),
    )
    current = asyncio.run(DemoDictamenRepository().get("D-00132"))

    with pytest.raises(ValidationError, match="no puede estar"):
        asyncio.run(controller.update_dictaminacion(current, value))


def test_real_update_skips_put_when_dictaminacion_is_unchanged():
    class RejectingUpdateRepository:
        async def update(self, clave, payload):
            raise AssertionError("An unchanged value must not trigger a PUT.")

    controller = DictamenController(
        DemoDictamenRepository(),
        DemoAlumnoRepository(),
        RecordingPdfGenerator(),
        require_admin=authenticated_store().require_admin,
        update_repository=RejectingUpdateRepository(),
        search_repository=DemoDictamenRepository(),
    )
    current = asyncio.run(DemoDictamenRepository().get("D-00132"))

    result = asyncio.run(
        controller.update_dictaminacion(
            current,
            f"  {current.dictaminacion}  ",
        )
    )

    assert result is current


@pytest.mark.parametrize(
    "changed_field",
    ["clave", "boleta", "alumno", "fecha", "anio"],
)
def test_real_update_rejects_backend_changes_to_immutable_metadata(changed_field):
    current = asyncio.run(DemoDictamenRepository().get("D-00132"))
    values = {
        "clave": "CSE-OTHER-26",
        "boleta": "2026999999",
        "alumno": "OTRO ALUMNO",
        "fecha": date(2026, 1, 1),
        "anio": 2026,
    }

    class InvalidUpdateRepository:
        async def update(self, clave, payload):
            data = {
                "clave": current.clave,
                "boleta": current.boleta,
                "alumno": current.alumno,
                "fecha": current.fecha,
                "anio": current.anio,
                "dictaminacion": payload.dictaminacion,
            }
            data[changed_field] = values[changed_field]
            return Dictamen(**data)

    controller = DictamenController(
        DemoDictamenRepository(),
        DemoAlumnoRepository(),
        RecordingPdfGenerator(),
        require_admin=authenticated_store().require_admin,
        update_repository=InvalidUpdateRepository(),
        search_repository=DemoDictamenRepository(),
    )

    with pytest.raises(UnexpectedResponseError):
        asyncio.run(controller.update_dictaminacion(current, "Nuevo valor"))


def test_generate_pdf_calls_the_generator_once_and_returns_the_exact_document():
    document = GeneratedDocument(
        filename="2024320678_dictamen_2026-08-30.pdf",
        content=b"%PDF-1.7 test",
        is_simulation=False,
    )
    pdf_generator = RecordingPdfGenerator(document)
    controller = DictamenController(
        DemoDictamenRepository(),
        DemoAlumnoRepository(),
        pdf_generator,
        require_admin=authenticated_store().require_admin,
        search_repository=DemoDictamenRepository(),
    )
    request = PdfRequest(
        dictamen=Dictamen(
            "D-00132",
            "2024320678",
            "Ana L\u00f3pez Mart\u00ednez",
            date(2026, 8, 30),
            2026,
            "Nueva causa",
        ),
        director="Dra. Mar\u00eda Del Carmen",
        fecha_sesion=date(2026, 12, 11),
    )

    result = asyncio.run(controller.generate_pdf(request))

    assert result is document
    assert pdf_generator.calls == [request]


def test_prepare_updated_pdf_request_uses_the_final_dictamen_and_captured_pdf_context():
    controller = build_controller()
    updated = Dictamen(
        "CSE-0001-26",
        "2024320678",
        "Ana L\u00f3pez Mart\u00ednez",
        date(2026, 8, 30),
        2026,
        "Nueva causa final",
    )

    request = controller.prepare_updated_pdf_request(
        updated,
        director="  Dra. Mar\u00eda Del Carmen  ",
        fecha_sesion=date(2026, 12, 11),
    )

    assert request.dictamen is updated
    assert request.director == "Dra. Mar\u00eda Del Carmen"
    assert request.fecha_sesion == date(2026, 12, 11)
    assert request.materias == ()


def test_prepare_updated_pdf_request_rejects_a_blank_director():
    controller = build_controller()
    updated = asyncio.run(DemoDictamenRepository().get("D-00132"))

    with pytest.raises(ValidationError, match="director|Director"):
        controller.prepare_updated_pdf_request(
            updated,
            director="   ",
            fecha_sesion=date(2026, 12, 11),
        )


def test_prepare_updated_pdf_request_rejects_an_invalid_session_date():
    controller = build_controller()
    updated = asyncio.run(DemoDictamenRepository().get("D-00132"))

    with pytest.raises(ValidationError, match="fecha de sesi"):
        controller.prepare_updated_pdf_request(
            updated,
            director="Dra. Mar\u00eda Del Carmen",
            fecha_sesion="11 DE DICIEMBRE",
        )


def test_prepare_updated_pdf_request_requires_admin_before_validation():
    normal_store = authenticated_store(is_admin=False)
    controller = DictamenController(
        DemoDictamenRepository(),
        DemoAlumnoRepository(),
        RecordingPdfGenerator(),
        require_admin=normal_store.require_admin,
        search_repository=DemoDictamenRepository(),
    )
    updated = asyncio.run(DemoDictamenRepository().get("D-00132"))

    with pytest.raises(AuthorizationError):
        controller.prepare_updated_pdf_request(
            updated,
            director="   ",
            fecha_sesion="11 DE DICIEMBRE",
        )


class RecordingMutationRepository:
    def __init__(self, current):
        self.current = current
        self.calls = []

    async def create(self, payload):
        self.calls.append(("create", payload))
        return self.current

    async def update(self, clave, payload):
        self.calls.append(("update", clave, payload))
        return Dictamen(
            self.current.clave,
            self.current.boleta,
            self.current.alumno,
            self.current.fecha,
            self.current.anio,
            payload.dictaminacion,
        )

    async def delete_many(self, claves):
        self.calls.append(("delete", tuple(claves)))
        return len(claves)


class RejectingGenerationPdfGenerator:
    def __init__(self):
        self.calls = []

    async def generate(self, request):
        self.calls.append(request)
        raise AssertionError("An unauthorized mutation must not generate a PDF.")


@pytest.mark.parametrize(
    "operation",
    [
        "create",
        "update",
        "update_dictaminacion",
        "prepare_updated_pdf_request",
        "delete_dictamenes",
    ],
)
def test_normal_user_mutations_are_rejected_before_any_collaborator(operation):
    base_repository = DemoDictamenRepository()
    current = asyncio.run(base_repository.get("D-00132"))
    alumno = asyncio.run(DemoAlumnoRepository().get_inscrito("2024320678"))
    repository = RecordingMutationRepository(current)
    pdf_generator = RejectingGenerationPdfGenerator()
    normal_store = authenticated_store(is_admin=False)
    controller = DictamenController(
        repository,
        DemoAlumnoRepository(),
        pdf_generator,
        require_admin=normal_store.require_admin,
        create_repository=repository,
        search_repository=DemoDictamenRepository(),
        update_repository=repository,
        delete_repository=repository,
    )

    with pytest.raises(AuthorizationError):
        if operation == "create":
            asyncio.run(
                controller.create(
                    alumno=alumno,
                    dictaminacion="Artículo 56",
                    director="Dirección ESIQIE",
                    materias=(),
                    reference=date(2026, 8, 29),
                    fecha_sesion=date(2026, 12, 11),
                )
            )
        elif operation == "update":
            asyncio.run(controller.update(current.clave, "Nueva causa"))
        elif operation == "update_dictaminacion":
            asyncio.run(controller.update_dictaminacion(current, "Nueva causa"))
        elif operation == "prepare_updated_pdf_request":
            controller.prepare_updated_pdf_request(
                current,
                director="Direcci\u00f3n ESIQIE",
                fecha_sesion=date(2026, 12, 11),
            )
        else:
            asyncio.run(controller.delete_dictamenes((current,)))

    assert repository.calls == []
    assert pdf_generator.calls == []


def test_normal_user_can_query_student_candidates():
    normal_store = authenticated_store(is_admin=False)
    controller = DictamenController(
        DemoDictamenRepository(),
        DemoAlumnoRepository(),
        RecordingPdfGenerator(),
        require_admin=normal_store.require_admin,
        search_repository=DemoDictamenRepository(),
    )

    candidate = asyncio.run(
        controller.find_student_candidate("inscrito", "2024320678", "20271")
    )

    assert candidate.alumno.boleta == "2024320678"


def test_normal_user_can_query_ruling_pages():
    normal_store = authenticated_store(is_admin=False)
    controller = DictamenController(
        DemoDictamenRepository(),
        DemoAlumnoRepository(),
        RecordingPdfGenerator(),
        require_admin=normal_store.require_admin,
        search_repository=DemoDictamenRepository(),
    )

    page = asyncio.run(
        controller.search_page(DictamenFilter(anio=2025), page=1)
    )

    assert page.total == 2
