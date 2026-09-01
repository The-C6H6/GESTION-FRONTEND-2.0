from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date

from esiqie_dictamenes.core.errors import (
    NotFoundError,
    UnexpectedResponseError,
    ValidationError,
)
from esiqie_dictamenes.features.alumnos.models import AlumnoDictaminable, Inscrito
from esiqie_dictamenes.features.alumnos.repository import (
    InscritoRepository,
    ReprobadoRepository,
)

from .models import (
    Dictamen,
    DictamenCreate,
    DictamenFilter,
    DictamenPage,
    DictamenUpdate,
    GeneratedDocument,
    MateriaElegible,
    MateriaReprobada,
    PdfRequest,
)
from .pdf import PdfGenerator
from .periodos import eligible_subjects
from .repository import (
    DictamenCreateRepository,
    DictamenDeleteRepository,
    DictamenRepository,
    DictamenSearchRepository,
    DictamenUpdateRepository,
)


@dataclass(frozen=True)
class CreatedDictamen:
    dictamen: Dictamen
    api_payload: DictamenCreate
    pdf_request: PdfRequest


@dataclass(frozen=True)
class StudentCandidate:
    alumno: AlumnoDictaminable
    materias: tuple[MateriaElegible, ...]
    total_reprobadas: int


class DictamenController:
    def __init__(
        self,
        repository: DictamenRepository,
        alumno_repository: InscritoRepository,
        pdf_generator: PdfGenerator,
        *,
        require_admin: Callable[[], None],
        reprobado_repository: ReprobadoRepository | None = None,
        create_repository: DictamenCreateRepository | None = None,
        search_repository: DictamenSearchRepository,
        update_repository: DictamenUpdateRepository | None = None,
        delete_repository: DictamenDeleteRepository | None = None,
    ) -> None:
        self._repository = repository
        self._alumno_repository = alumno_repository
        self._reprobado_repository = reprobado_repository or alumno_repository
        self._create_repository = create_repository or repository
        self._search_repository = search_repository
        self._update_repository = update_repository or repository
        self._delete_repository = delete_repository or repository
        self._pdf_generator = pdf_generator
        self._require_admin = require_admin

    async def find_student_candidate(
        self,
        source: str,
        query: str,
        period: str,
    ) -> StudentCandidate:
        normalized = query.strip()
        if not normalized:
            raise ValidationError("Escribe el número de boleta.")
        if source == "inscrito":
            inscrito = await self._alumno_repository.get_inscrito(normalized)
            return StudentCandidate(self._from_inscrito(inscrito), (), 0)
        if source == "reprobado":
            records = await self._reprobado_repository.search_reprobados(
                boleta=normalized
            )
            if not records:
                raise NotFoundError(
                    "No se encontraron materias reprobadas para la boleta indicada."
                )
            return self._candidate_from_reprobados(records, period)
        raise ValidationError("Selecciona un tipo de alumno válido.")

    async def find_eligible_reprobados(
        self, query: str, period: str
    ) -> tuple[MateriaElegible, ...]:
        return (await self.find_reprobado_candidate(query, period)).materias

    async def find_reprobado_candidate(
        self, query: str, period: str
    ) -> StudentCandidate:
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
        return self._candidate_from_reprobados(records, period)

    @staticmethod
    def _from_inscrito(inscrito: Inscrito) -> AlumnoDictaminable:
        return AlumnoDictaminable(
            boleta=inscrito.boleta,
            nombre=inscrito.nombre,
            carrera=inscrito.carrera,
        )

    @staticmethod
    def _candidate_from_reprobados(
        records: Sequence[MateriaReprobada],
        period: str,
    ) -> StudentCandidate:
        first = records[0]
        alumno = AlumnoDictaminable(
            boleta=first.boleta,
            nombre=first.nombre,
            carrera=first.carrera,
        )
        return StudentCandidate(
            alumno,
            eligible_subjects(period, records),
            len(records),
        )

    async def search_page(
        self,
        filters: DictamenFilter,
        *,
        page: int,
    ) -> DictamenPage:
        if (filters.boleta is None) == (filters.anio is None):
            raise ValidationError("Selecciona un criterio de bÃºsqueda vÃ¡lido.")
        if page < 1:
            raise ValidationError("La pÃ¡gina solicitada no es vÃ¡lida.")
        limit = 100
        return await self._search_repository.search_page(
            filters,
            skip=(page - 1) * limit,
            limit=limit,
        )

    async def update(self, clave: str, dictaminacion: str) -> Dictamen:
        self._require_admin()
        return await self._update(clave, dictaminacion)

    async def _update(self, clave: str, dictaminacion: str) -> Dictamen:
        normalized = dictaminacion.strip()
        if not normalized:
            raise ValidationError("Escribe la nueva dictaminación.")
        return await self._repository.update(clave, DictamenUpdate(normalized))

    async def update_dictaminacion(
        self,
        current: Dictamen,
        dictaminacion: object,
    ) -> Dictamen:
        self._require_admin()
        if not isinstance(dictaminacion, str) or not dictaminacion.strip():
            raise ValidationError("La dictaminación no puede estar vacía.")
        normalized = dictaminacion.strip()
        if normalized == current.dictaminacion:
            return current

        updated = await self._update_repository.update(
            current.clave,
            DictamenUpdate(normalized),
        )
        immutable_current = (
            current.clave,
            current.boleta,
            current.alumno,
            current.fecha,
            current.anio,
        )
        immutable_updated = (
            updated.clave,
            updated.boleta,
            updated.alumno,
            updated.fecha,
            updated.anio,
        )
        if immutable_updated != immutable_current:
            raise UnexpectedResponseError()
        return updated

    def prepare_updated_pdf_request(
        self,
        dictamen: Dictamen,
        *,
        director: object,
        fecha_sesion: object,
    ) -> PdfRequest:
        self._require_admin()
        if not isinstance(director, str) or not director.strip():
            raise ValidationError("El director es obligatorio.")
        if not isinstance(fecha_sesion, date):
            raise ValidationError("Selecciona la fecha de sesión en el calendario.")
        return PdfRequest(
            dictamen=dictamen,
            director=director.strip(),
            fecha_sesion=fecha_sesion,
            materias=(),
        )

    async def generate_pdf(self, request: PdfRequest) -> GeneratedDocument:
        return await self._pdf_generator.generate(request)

    async def create(
        self,
        alumno: AlumnoDictaminable | Inscrito,
        dictaminacion: str,
        director: str,
        materias: Sequence[MateriaElegible],
        reference: date,
        fecha_sesion: date,
    ) -> CreatedDictamen:
        self._require_admin()
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
        dictamen = await self._create_repository.create(payload)
        pdf_request = PdfRequest(
            dictamen=dictamen,
            director=director.strip(),
            fecha_sesion=fecha_sesion,
            materias=tuple(materias),
        )
        return CreatedDictamen(dictamen, payload, pdf_request)

    async def delete_dictamenes(self, dictamenes: Sequence[Dictamen]) -> int:
        self._require_admin()
        if not dictamenes:
            raise ValidationError("Selecciona al menos un dictamen.")
        claves = tuple(dict.fromkeys(dictamen.clave for dictamen in dictamenes))
        return await self._delete_repository.delete_many(claves)
