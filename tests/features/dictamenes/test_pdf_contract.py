import asyncio
from datetime import date

from esiqie_dictamenes.features.dictamenes.models import (
    Dictamen,
    MateriaElegible,
    PdfRequest,
)
from esiqie_dictamenes.infrastructure.demo.pdf_generator import DemoPdfGenerator


def test_demo_pdf_generator_reports_simulation_without_fake_pdf_download():
    request = PdfRequest(
        dictamen=Dictamen(
            clave="D-00132",
            boleta="2024320678",
            alumno="Ana López Martínez",
            fecha=date(2026, 8, 24),
            anio=2026,
            dictaminacion="Artículo 56",
        ),
        director="Dr. Nombre Apellido",
        materias=(MateriaElegible("Cálculo diferencial", 20252, 19),),
    )

    document = asyncio.run(DemoPdfGenerator().generate(request))

    assert document.filename == "2024320678_dictamen.pdf"
    assert document.content == b""
    assert document.is_simulation is True
