from datetime import date
from typing import Protocol

from .models import GeneratedDocument, PdfRequest


_MONTHS = (
    "ENERO",
    "FEBRERO",
    "MARZO",
    "ABRIL",
    "MAYO",
    "JUNIO",
    "JULIO",
    "AGOSTO",
    "SEPTIEMBRE",
    "OCTUBRE",
    "NOVIEMBRE",
    "DICIEMBRE",
)

_SESSION_PARAGRAPH = (
    "CON FUNDAMENTO EN LOS ARTÍCULOS 52, 55, 57 Y 60 DEL REGLAMENTO "
    "GENERAL DE ESTUDIOS DEL INSTITUTO POLITÉCNICO NACIONAL, LE COMUNICO "
    "EL RESULTADO DEL DICTAMEN RELATIVO A SU SOLICITUD EMITIDO POR LA "
    "COMISIÓN DE SITUACIÓN ESCOLAR DEL CONSEJO TÉCNICO CONSULTIVO ESCOLAR, "
    "EN LA SESIÓN ORDINARIA CELEBRADA EL {fecha_sesion}."
)


def format_session_date(value: date) -> str:
    """Format a session date for the institutional ruling text, without its year."""
    if not isinstance(value, date):
        raise TypeError("Session date must be a date object.")
    return f"{value.day} DE {_MONTHS[value.month - 1]}"


def build_session_paragraph(fecha_sesion: date) -> str:
    return _SESSION_PARAGRAPH.format(
        fecha_sesion=format_session_date(fecha_sesion)
    )


class PdfGenerator(Protocol):
    async def generate(self, request: PdfRequest) -> GeneratedDocument: ...
