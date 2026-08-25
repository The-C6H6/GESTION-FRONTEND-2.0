from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Dictamen:
    clave: str
    boleta: str
    alumno: str
    fecha: date
    anio: int
    dictaminacion: str


@dataclass(frozen=True)
class DictamenFilter:
    boleta: str | None = None
    anio: int | None = None


@dataclass(frozen=True)
class DictamenCreate:
    boleta: str
    nombre: str
    fecha: date
    anio: int
    dictaminacion: str


@dataclass(frozen=True)
class DictamenUpdate:
    dictaminacion: str


@dataclass(frozen=True)
class MateriaReprobada:
    materia: str
    periodo_reprobada: int
    boleta: str = ""
    nombre: str = ""


@dataclass(frozen=True)
class MateriaElegible:
    materia: str
    periodo_reprobada: int
    diferencia: int


@dataclass(frozen=True)
class PdfRequest:
    dictamen: Dictamen
    director: str
    materias: tuple[MateriaElegible, ...] = ()


@dataclass(frozen=True)
class GeneratedDocument:
    filename: str
    content: bytes
    is_simulation: bool
