from datetime import date

from esiqie_dictamenes.features.alumnos.models import Inscrito
from esiqie_dictamenes.features.dictamenes.models import Dictamen, MateriaReprobada


DICTAMENES = (
    Dictamen("D-00081", "2024320678", "Ana López Martínez", date(2024, 8, 14), 2024, "Artículo 52"),
    Dictamen("D-00132", "2024320678", "Ana López Martínez", date(2025, 8, 14), 2025, "Artículo 54"),
    Dictamen("D-00201", "2024320678", "Ana López Martínez", date(2026, 8, 14), 2026, "Artículo 56"),
    Dictamen("D-00234", "2021320863", "Bruno Sánchez Pérez", date(2025, 3, 10), 2025, "Artículo 47"),
)

INSCRITOS = {
    "2024320678": Inscrito(
        boleta="2024320678",
        nombre="Ana López Martínez",
        carrera="Ingeniería Química Industrial",
        plan_estud=2021,
        especialidad="Procesos Industriales",
        secuencias="5IM1",
        turno="Matutino",
        genero="Femenino",
        edad=21,
        promedio=8.74,
        dictamen_vigente="NO",
        periodo_escolar_ingreso="20231",
        periodos_cursados=7,
        semestre_nivel_inscrito=6,
        no_cursadas=1,
        reprobadas=2,
        desfasadas=0,
        periodo_en_que_reprobo=20242,
        materias_inscritas=6,
        materias_reprobadas_no_inscritas=1,
        avance=68.5,
        carga_minima=24,
        carga_media=36,
        carga_maxima=48,
        creditos_inscritos=42,
        creditos_de_reprobadas_inscritas=6,
        creditos_de_reprobadas_no_inscritas=6,
        total_de_creditos=310,
        posible_irregularidad=None,
    )
}

REPROBADOS = (
    MateriaReprobada(
        "Cálculo diferencial",
        20252,
        "2024320678",
        "Ana López Martínez",
        "Ingeniería Química Industrial",
    ),
    MateriaReprobada(
        "Termodinámica",
        20243,
        "2024320678",
        "Ana López Martínez",
        "Ingeniería Química Industrial",
    ),
    MateriaReprobada(
        "Álgebra lineal",
        20242,
        "2024320678",
        "Ana López Martínez",
        "Ingeniería Química Industrial",
    ),
)
