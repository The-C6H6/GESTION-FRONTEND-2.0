import asyncio
from datetime import date
from types import SimpleNamespace

import pytest

from esiqie_dictamenes.core.errors import NotFoundError, ValidationError
from esiqie_dictamenes.features.dictamenes.controller import DictamenController
from esiqie_dictamenes.features.dictamenes.models import (
    DictamenFilter,
    MateriaReprobada,
)
from esiqie_dictamenes.infrastructure.demo.alumno_repository import DemoAlumnoRepository
from esiqie_dictamenes.infrastructure.demo.dictamen_repository import DemoDictamenRepository
from esiqie_dictamenes.infrastructure.demo.pdf_generator import DemoPdfGenerator


def build_controller():
    return DictamenController(
        DemoDictamenRepository(), DemoAlumnoRepository(), DemoPdfGenerator()
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
        DemoPdfGenerator(),
        reprobado_repository=RejectingReprobadoRepository(),
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
                    boleta=boleta,
                    nombre="Alumno solo reprobado",
                    carrera="Ingeniería Química Industrial",
                ),
            )

    reprobados = RecordingReprobadoRepository()
    controller = DictamenController(
        DemoDictamenRepository(),
        RejectingInscritoRepository(),
        DemoPdfGenerator(),
        reprobado_repository=reprobados,
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
        DemoPdfGenerator(),
        reprobado_repository=EmptyReprobadoRepository(),
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
    controller = build_controller()

    with pytest.raises(ValidationError, match="Selecciona"):
        asyncio.run(controller.delete_many(()))


def test_search_returns_all_rulings_for_the_requested_boleta():
    controller = build_controller()

    result = asyncio.run(controller.search(DictamenFilter(boleta="2024320678")))

    assert len(result) == 3


def test_update_preserves_read_only_ruling_metadata():
    controller = build_controller()

    result = asyncio.run(controller.update("D-00132", "Causa actualizada"))

    assert result.clave == "D-00132"
    assert result.boleta == "2024320678"
    assert result.anio == 2025
    assert result.dictaminacion == "Causa actualizada"


def test_update_generates_a_new_pdf_simulation_automatically():
    controller = build_controller()

    result = asyncio.run(controller.update_and_generate("D-00132", "Nueva causa"))

    assert result.dictamen.dictaminacion == "Nueva causa"
    assert result.document.filename == "2024320678_dictamen.pdf"
    assert result.document.is_simulation is True
