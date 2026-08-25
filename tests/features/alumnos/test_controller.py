import asyncio

import pytest

from esiqie_dictamenes.core.errors import ValidationError
from esiqie_dictamenes.features.alumnos.controller import AlumnoController
from esiqie_dictamenes.infrastructure.demo.alumno_repository import DemoAlumnoRepository


def test_find_inscrito_returns_the_matching_student():
    controller = AlumnoController(DemoAlumnoRepository())

    result = asyncio.run(controller.find_inscrito("2024320678"))

    assert result.nombre == "Ana López Martínez"


def test_find_inscrito_requires_a_boleta():
    class RejectingRepository:
        async def get_inscrito(self, boleta):
            raise AssertionError("An invalid boleta must not reach the repository.")

    controller = AlumnoController(RejectingRepository())

    with pytest.raises(ValidationError, match="boleta"):
        asyncio.run(controller.find_inscrito("   "))
