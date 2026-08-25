import asyncio
from datetime import date

import pytest

from esiqie_dictamenes.core.errors import ValidationError
from esiqie_dictamenes.features.dictamenes.controller import DictamenController
from esiqie_dictamenes.features.dictamenes.models import DictamenFilter
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


def test_create_keeps_director_out_of_the_api_payload_and_in_pdf_context():
    controller = build_controller()
    alumno = asyncio.run(DemoAlumnoRepository().get_inscrito("2024320678"))

    result = asyncio.run(
        controller.create(
            alumno=alumno,
            dictaminacion="Artículo 56",
            director="Dr. Dirección Escolar",
            materias=(),
            reference=date(2026, 8, 24),
        )
    )

    assert result.dictamen.boleta == "2024320678"
    assert result.dictamen.anio == 2026
    assert result.document.filename == "2024320678_dictamen.pdf"
    assert result.pdf_request.director == "Dr. Dirección Escolar"
    assert not hasattr(result.api_payload, "director")


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
