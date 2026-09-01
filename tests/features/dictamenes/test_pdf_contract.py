from datetime import date

import pytest

from esiqie_dictamenes.features.dictamenes import pdf
from esiqie_dictamenes.features.dictamenes.models import Dictamen


@pytest.mark.parametrize(
    ("month", "name"),
    [
        (1, "ENERO"),
        (2, "FEBRERO"),
        (3, "MARZO"),
        (4, "ABRIL"),
        (5, "MAYO"),
        (6, "JUNIO"),
        (7, "JULIO"),
        (8, "AGOSTO"),
        (9, "SEPTIEMBRE"),
        (10, "OCTUBRE"),
        (11, "NOVIEMBRE"),
        (12, "DICIEMBRE"),
    ],
)
def test_session_date_formatter_uses_spanish_month_without_year(month, name):
    result = pdf.format_session_date(date(2026, month, 11))

    assert result == f"11 DE {name}"
    assert "2026" not in result


def test_pdf_filename_uses_the_dictamen_boleta_and_issue_date():
    dictamen = Dictamen(
        clave="D-00132",
        boleta="2021320863",
        alumno="Ana LÃ³pez MartÃ­nez",
        fecha=date(2026, 8, 30),
        anio=2026,
        dictaminacion="ArtÃ­culo 56",
    )

    assert pdf.build_pdf_filename(dictamen) == "2021320863_dictamen_2026-08-30.pdf"


def test_session_paragraph_inserts_the_formatted_date_once():
    result = pdf.build_session_paragraph(date(2026, 12, 11))

    assert result == (
        "CON FUNDAMENTO EN LOS ARTÍCULOS 52, 55, 57 Y 60 DEL REGLAMENTO "
        "GENERAL DE ESTUDIOS DEL INSTITUTO POLITÉCNICO NACIONAL, LE COMUNICO "
        "EL RESULTADO DEL DICTAMEN RELATIVO A SU SOLICITUD EMITIDO POR LA "
        "COMISIÓN DE SITUACIÓN ESCOLAR DEL CONSEJO TÉCNICO CONSULTIVO ESCOLAR, "
        "EN LA SESIÓN ORDINARIA CELEBRADA EL 11 DE DICIEMBRE."
    )
