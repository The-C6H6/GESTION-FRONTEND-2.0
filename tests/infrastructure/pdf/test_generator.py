import asyncio
import shutil
from dataclasses import replace
from datetime import date

import pymupdf
import pytest
from fpdf import FPDF

from esiqie_dictamenes.core.errors import PdfGenerationError
from esiqie_dictamenes.core.paths import project_assets_dir
from esiqie_dictamenes.features.dictamenes.models import Dictamen, PdfRequest
from esiqie_dictamenes.features.dictamenes.pdf import build_session_paragraph
from esiqie_dictamenes.infrastructure.pdf.generator import RealPdfGenerator


REQUIRED_ASSETS = ("ipn_logo.jpg", "logo_esiqie.png", "imagen_fondo.png")


def _request() -> PdfRequest:
    return PdfRequest(
        dictamen=Dictamen(
            clave="D-00132",
            boleta="2024320678",
            alumno="Ana López Martínez Á É Í Ó Ú á é í ó ú Ñ ñ ü",
            fecha=date(2026, 8, 24),
            anio=2026,
            dictaminacion=(
                "Se autoriza la reinscripción conforme al Artículo 56."
            ),
        ),
        director="Dra. Iñés Muñoz Güemes",
        fecha_sesion=date(2026, 12, 11),
        materias=(),
    )


def _extract_text(content: bytes) -> tuple[pymupdf.Document, str]:
    document = pymupdf.open(stream=content, filetype="pdf")
    text = " ".join(
        " ".join(page.get_text().split()) for page in document
    )
    return document, text


def test_generate_returns_one_real_in_memory_pdf_without_a_subject_table():
    request = _request()

    result = asyncio.run(RealPdfGenerator(project_assets_dir()).generate(request))
    pdf, text = _extract_text(result.content)

    try:
        assert result.content.startswith(b"%PDF-")
        assert len(result.content) > 1_000
        assert result.is_simulation is False
        assert result.filename == "2024320678_dictamen_2026-08-24.pdf"
        assert pdf.page_count == 1
        assert pdf[0].rect.width == pytest.approx(595.28, abs=0.1)
        assert pdf[0].rect.height == pytest.approx(841.89, abs=0.1)
        assert request.dictamen.clave in text
        assert request.dictamen.alumno in text
        assert request.dictamen.boleta in text
        assert request.dictamen.dictaminacion in text
        assert request.director in text
        assert build_session_paragraph(request.fecha_sesion) in text
        assert "Á É Í Ó Ú á é í ó ú Ñ ñ ü" in text
        assert "Materia Desfasada" not in text
        assert "Periodo Reprobada" not in text
        assert "Intentos Ordinario" not in text
        assert "Inscrita" not in text
    finally:
        pdf.close()


def test_generate_keeps_a_wrapped_director_signature_block_on_one_page():
    base_request = _request()
    request = replace(
        base_request,
        dictamen=replace(
            base_request.dictamen,
            dictaminacion="Se autoriza la reinscripción. " * 90,
        ),
        director=(
            "DIRECTORA INÉS "
            + "NOMBRE INSTITUCIONAL EXTENSO " * 28
            + "FIN DE FIRMA"
        ),
    )

    result = asyncio.run(RealPdfGenerator(project_assets_dir()).generate(request))
    pdf = pymupdf.open(stream=result.content, filetype="pdf")

    try:
        page_texts = [" ".join(page.get_text().split()) for page in pdf]
        signature_pages = {
            page_number
            for page_number, text in enumerate(page_texts)
            if any(
                marker in text
                for marker in (
                    "ATENTAMENTE",
                    "LA TÉCNICA AL SERVICIO DE LA PATRIA",
                    "DIRECTORA INÉS",
                    "FIN DE FIRMA",
                    "DIRECTOR(A)",
                )
            )
        }

        assert len(signature_pages) == 1
    finally:
        pdf.close()


@pytest.mark.parametrize("missing_asset", REQUIRED_ASSETS)
def test_generate_hides_which_required_asset_is_missing(tmp_path, missing_asset):
    source_assets = project_assets_dir()
    for asset_name in REQUIRED_ASSETS:
        if asset_name != missing_asset:
            shutil.copy2(source_assets / asset_name, tmp_path / asset_name)

    with pytest.raises(
        PdfGenerationError,
        match=r"^No fue posible generar el documento PDF\.$",
    ) as error:
        asyncio.run(RealPdfGenerator(tmp_path).generate(_request()))

    assert missing_asset not in str(error.value)


def test_generate_hides_unexpected_renderer_failures(monkeypatch):
    def fail_output(*args, **kwargs):
        raise RuntimeError("sensitive renderer detail")

    monkeypatch.setattr(FPDF, "output", fail_output)

    with pytest.raises(
        PdfGenerationError,
        match=r"^No fue posible generar el documento PDF\.$",
    ) as error:
        asyncio.run(RealPdfGenerator(project_assets_dir()).generate(_request()))

    assert "sensitive renderer detail" not in str(error.value)
