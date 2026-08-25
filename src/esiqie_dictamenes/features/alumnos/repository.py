from collections.abc import Sequence
from typing import Protocol

from esiqie_dictamenes.features.dictamenes.models import MateriaReprobada

from .models import Inscrito


class InscritoRepository(Protocol):
    async def get_inscrito(self, boleta: str) -> Inscrito: ...


class ReprobadoRepository(Protocol):
    async def search_reprobados(
        self, boleta: str | None = None, nombre: str | None = None
    ) -> Sequence[MateriaReprobada]: ...


class AlumnoRepository(InscritoRepository, ReprobadoRepository, Protocol):
    pass
