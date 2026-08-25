from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from esiqie_dictamenes.core.errors import NotFoundError, ValidationError
from esiqie_dictamenes.features.alumnos.models import Inscrito
from esiqie_dictamenes.features.alumnos.repository import (
    AlumnoRepository,
    ReprobadoRepository,
)

from .models import (
    Dictamen,
    DictamenCreate,
    DictamenFilter,
    DictamenUpdate,
    GeneratedDocument,
    MateriaElegible,
    PdfRequest,
)
from .pdf import PdfGenerator
from .periodos import eligible_subjects
from .repository import DictamenRepository


@dataclass(frozen=True)
class CreatedDictamen:
    dictamen: Dictamen
    api_payload: DictamenCreate
    pdf_request: PdfRequest
    document: GeneratedDocument


@dataclass(frozen=True)
class ReprobadoCandidate:
    alumno: Inscrito
    materias: tuple[MateriaElegible, ...]
    total_reprobadas: int


@dataclass(frozen=True)
class UpdatedDictamen:
    dictamen: Dictamen
    document: GeneratedDocument


class DictamenController:
    def __init__(
        self,
        repository: DictamenRepository,
        alumno_repository: AlumnoRepository,
        pdf_generator: PdfGenerator,
        reprobado_repository: ReprobadoRepository | None = None,
    ) -> None:
        self._repository = repository
        self._alumno_repository = alumno_repository
        self._reprobado_repository = reprobado_repository or alumno_repository
        self._pdf_generator = pdf_generator

    async def find_eligible_reprobados(
        self, query: str, period: str
    ) -> tuple[MateriaElegible, ...]:
        return (await self.find_reprobado_candidate(query, period)).materias

    async def find_reprobado_candidate(
        self, query: str, period: str
    ) -> ReprobadoCandidate:
        normalized = query.strip()
        if not normalized:
            raise ValidationError("Escribe una boleta o nombre de alumno.")
        if normalized.isdigit():
            records = await self._reprobado_repository.search_reprobados(
                boleta=normalized
            )
        else:
            records = await self._reprobado_repository.search_reprobados(
                nombre=normalized
            )
        if not records:
            raise NotFoundError("No se encontraron materias reprobadas para el alumno.")
        alumno = await self._alumno_repository.get_inscrito(records[0].boleta)
        return ReprobadoCandidate(
            alumno,
            eligible_subjects(period, records),
            len(records),
        )

    async def find_reprobado_candidate_for_student(
        self, alumno: Inscrito, period: str
    ) -> ReprobadoCandidate:
        records = await self._reprobado_repository.search_reprobados(
            boleta=alumno.boleta
        )
        return ReprobadoCandidate(
            alumno,
            eligible_subjects(period, records),
            len(records),
        )

    async def search(self, filters: DictamenFilter) -> Sequence[Dictamen]:
        return await self._repository.search(filters)

    async def get(self, clave: str) -> Dictamen:
        return await self._repository.get(clave)

    async def update(self, clave: str, dictaminacion: str) -> Dictamen:
        normalized = dictaminacion.strip()
        if not normalized:
            raise ValidationError("Escribe la nueva dictaminación.")
        return await self._repository.update(clave, DictamenUpdate(normalized))

    async def update_and_generate(
        self, clave: str, dictaminacion: str
    ) -> UpdatedDictamen:
        dictamen = await self.update(clave, dictaminacion)
        request = PdfRequest(
            dictamen=dictamen,
            director="Dirección ESIQIE",
            fecha_sesion=dictamen.fecha,
        )
        document = await self._pdf_generator.generate(request)
        return UpdatedDictamen(dictamen, document)

    async def create(
        self,
        alumno: Inscrito,
        dictaminacion: str,
        director: str,
        materias: Sequence[MateriaElegible],
        reference: date,
        fecha_sesion: date,
    ) -> CreatedDictamen:
        if not dictaminacion.strip() or not director.strip():
            raise ValidationError("Director y dictaminación son obligatorios.")
        if not isinstance(fecha_sesion, date):
            raise ValidationError("Selecciona la fecha de sesión en el calendario.")
        payload = DictamenCreate(
            boleta=alumno.boleta,
            nombre=alumno.nombre,
            fecha=reference,
            anio=reference.year,
            dictaminacion=dictaminacion.strip(),
        )
        dictamen = await self._repository.create(payload)
        pdf_request = PdfRequest(
            dictamen=dictamen,
            director=director.strip(),
            fecha_sesion=fecha_sesion,
            materias=tuple(materias),
        )
        document = await self._pdf_generator.generate(pdf_request)
        return CreatedDictamen(dictamen, payload, pdf_request, document)

    async def delete_many(self, claves: Sequence[str]) -> int:
        if not claves:
            raise ValidationError("Selecciona al menos un dictamen.")
        return await self._repository.delete_many(claves)
