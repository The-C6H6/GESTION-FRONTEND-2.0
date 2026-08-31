from collections.abc import Iterable
from datetime import date

from esiqie_dictamenes.core.errors import ValidationError

from .models import MateriaElegible, MateriaReprobada


def current_period(reference: date) -> str:
    semester = 2 if reference.month <= 6 else 1
    school_year = reference.year if reference.month <= 6 else reference.year + 1
    return f"{school_year}{semester}"


def validate_period(value: str) -> int:
    if len(value) != 5 or not value.isdigit() or value[-1] not in {"1", "2"}:
        raise ValidationError(
            "El periodo actual debe tener cinco dígitos y terminar en 1 o 2."
        )
    return int(value)


def eligible_subjects(
    period: str, subjects: Iterable[MateriaReprobada]
) -> tuple[MateriaElegible, ...]:
    current = validate_period(period)
    eligible: list[MateriaElegible] = []
    for subject in subjects:
        difference = current - subject.periodo_reprobada
        if 19 <= difference < 29:
            eligible.append(
                MateriaElegible(
                    materia=subject.materia,
                    periodo_reprobada=subject.periodo_reprobada,
                    diferencia=difference,
                    intentos_ordinario=subject.intentos_ordinario,
                    materia_inscrita=subject.materia_inscrita,
                )
            )
    return tuple(eligible)
