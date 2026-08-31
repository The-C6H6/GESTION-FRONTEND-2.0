from datetime import date

import pytest

from esiqie_dictamenes.core.errors import ValidationError
from esiqie_dictamenes.features.dictamenes.models import MateriaReprobada
from esiqie_dictamenes.features.dictamenes.periodos import (
    current_period,
    eligible_subjects,
    validate_period,
)


@pytest.mark.parametrize(
    ("reference", "expected"),
    [
        (date(2026, 1, 1), "20262"),
        (date(2026, 6, 30), "20262"),
        (date(2026, 7, 1), "20271"),
        (date(2026, 12, 31), "20271"),
    ],
)
def test_current_period_uses_the_school_year_boundary(reference, expected):
    assert current_period(reference) == expected


@pytest.mark.parametrize("value", ["", "2026", "202633", "20263", "abcde"])
def test_validate_period_rejects_invalid_current_periods(value):
    with pytest.raises(ValidationError, match="periodo actual"):
        validate_period(value)


def test_eligible_subjects_include_only_differences_from_19_through_28():
    subjects = (
        MateriaReprobada(
            "Fuera por 18", 20253, intentos_ordinario=1, materia_inscrita="NO"
        ),
        MateriaReprobada(
            "Límite inferior", 20252, intentos_ordinario=2, materia_inscrita="SI"
        ),
        MateriaReprobada(
            "Límite superior", 20243, intentos_ordinario=3, materia_inscrita=None
        ),
        MateriaReprobada(
            "Fuera por 29", 20242, intentos_ordinario=4, materia_inscrita="NO"
        ),
    )

    result = eligible_subjects("20271", subjects)

    assert [
        (
            item.materia,
            item.diferencia,
            item.intentos_ordinario,
            item.materia_inscrita,
        )
        for item in result
    ] == [
        ("Límite inferior", 19, 2, "SI"),
        ("Límite superior", 28, 3, None),
    ]
