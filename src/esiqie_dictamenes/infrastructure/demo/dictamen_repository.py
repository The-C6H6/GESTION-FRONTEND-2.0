from collections.abc import Sequence
from dataclasses import replace

from esiqie_dictamenes.core.errors import NotFoundError
from esiqie_dictamenes.features.dictamenes.models import (
    Dictamen,
    DictamenCreate,
    DictamenFilter,
    DictamenUpdate,
)

from .fixtures import DICTAMENES


class DemoDictamenRepository:
    def __init__(self) -> None:
        self._records = list(DICTAMENES)

    async def search(self, filters: DictamenFilter) -> Sequence[Dictamen]:
        return tuple(
            record
            for record in self._records
            if (not filters.boleta or record.boleta == filters.boleta)
            and (filters.anio is None or record.anio == filters.anio)
        )

    async def get(self, clave: str) -> Dictamen:
        for record in self._records:
            if record.clave == clave:
                return record
        raise NotFoundError("No se encontró el dictamen solicitado.")

    async def create(self, payload: DictamenCreate) -> Dictamen:
        record = Dictamen(
            clave=f"D-{len(self._records) + 1:05d}",
            boleta=payload.boleta,
            alumno=payload.nombre,
            fecha=payload.fecha,
            anio=payload.anio,
            dictaminacion=payload.dictaminacion,
        )
        self._records.append(record)
        return record

    async def update(self, clave: str, payload: DictamenUpdate) -> Dictamen:
        current = await self.get(clave)
        updated = replace(current, dictaminacion=payload.dictaminacion)
        self._records[self._records.index(current)] = updated
        return updated

    async def delete_many(self, claves: Sequence[str]) -> int:
        selected = set(claves)
        before = len(self._records)
        self._records = [record for record in self._records if record.clave not in selected]
        return before - len(self._records)
