from dataclasses import dataclass


@dataclass(frozen=True)
class AlumnoDictaminable:
    boleta: str
    nombre: str
    carrera: str


@dataclass(frozen=True)
class Inscrito:
    boleta: str
    nombre: str
    carrera: str
    plan_estud: int
    especialidad: str
    secuencias: str
    turno: str
    genero: str
    edad: int | None
    promedio: float
    dictamen_vigente: str
    periodo_escolar_ingreso: str
    periodos_cursados: int
    semestre_nivel_inscrito: int
    no_cursadas: int
    reprobadas: int
    desfasadas: int
    periodo_en_que_reprobo: int | None
    materias_inscritas: int
    materias_reprobadas_no_inscritas: int | None
    avance: float
    carga_minima: int
    carga_media: int
    carga_maxima: int
    creditos_inscritos: int
    creditos_de_reprobadas_inscritas: int
    creditos_de_reprobadas_no_inscritas: int
    total_de_creditos: int
    posible_irregularidad: str | None
