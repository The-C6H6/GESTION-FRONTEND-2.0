from datetime import date
from pathlib import Path
from typing import Protocol

from .models import Dictamen, GeneratedDocument, PdfRequest


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


def format_dictamen_date(value: date) -> str:
    """Format the issued ruling date in the historical Spanish document style."""
    if not isinstance(value, date):
        raise TypeError("Dictamen date must be a date object.")
    return f"{value.day} de {_MONTHS[value.month - 1].capitalize()} de {value.year}"


def build_session_paragraph(fecha_sesion: date) -> str:
    return _SESSION_PARAGRAPH.format(
        fecha_sesion=format_session_date(fecha_sesion)
    )


def build_pdf_filename(dictamen: Dictamen) -> str:
    return f"{dictamen.boleta}_dictamen_{dictamen.fecha.isoformat()}.pdf"


class PdfGenerator(Protocol):
    async def generate(self, request: PdfRequest) -> GeneratedDocument: ...


class PdfDocumentStore(Protocol):
    def validate_destination(self, destination: str | Path) -> Path: ...

    async def save(self, destination: str | Path, document: bytes) -> Path: ...
