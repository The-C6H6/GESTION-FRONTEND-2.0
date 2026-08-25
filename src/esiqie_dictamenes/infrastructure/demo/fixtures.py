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
        edad=21,
        genero="Femenino",
        promedio=8.74,
        creditos_inscritos=42,
        periodo_en_que_reprobo=20242,
        reprobadas=2,
    )
}

REPROBADOS = (
    MateriaReprobada("Cálculo diferencial", 20252, "2024320678", "Ana López Martínez"),
    MateriaReprobada("Termodinámica", 20243, "2024320678", "Ana López Martínez"),
    MateriaReprobada("Álgebra lineal", 20242, "2024320678", "Ana López Martínez"),
)
