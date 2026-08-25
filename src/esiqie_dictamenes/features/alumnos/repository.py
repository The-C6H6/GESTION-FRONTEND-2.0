from collections.abc import Sequence
from typing import Protocol

from esiqie_dictamenes.features.dictamenes.models import MateriaReprobada

from .models import Inscrito


class AlumnoRepository(Protocol):
    async def get_inscrito(self, boleta: str) -> Inscrito: ...

    async def search_reprobados(
        self, boleta: str | None = None, nombre: str | None = None
    ) -> Sequence[MateriaReprobada]: ...
