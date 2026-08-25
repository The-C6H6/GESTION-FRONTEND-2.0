from dataclasses import dataclass


@dataclass(frozen=True)
class Inscrito:
    boleta: str
    nombre: str
    carrera: str
    edad: int | None
    genero: str
    promedio: float
    creditos_inscritos: int
    periodo_en_que_reprobo: int | None
    reprobadas: int
