from collections.abc import Sequence

from esiqie_dictamenes.core.errors import NotFoundError
from esiqie_dictamenes.features.alumnos.models import Inscrito
from esiqie_dictamenes.features.dictamenes.models import MateriaReprobada

from .fixtures import INSCRITOS, REPROBADOS


class DemoAlumnoRepository:
    async def get_inscrito(self, boleta: str) -> Inscrito:
        try:
            return INSCRITOS[boleta]
        except KeyError as error:
            raise NotFoundError("No se encontró un alumno inscrito con esa boleta.") from error

    async def search_reprobados(
        self, boleta: str | None = None, nombre: str | None = None
    ) -> Sequence[MateriaReprobada]:
        normalized_name = nombre.casefold() if nombre else None
        return tuple(
            record
            for record in REPROBADOS
            if (not boleta or record.boleta == boleta)
            and (not normalized_name or normalized_name in record.nombre.casefold())
        )
