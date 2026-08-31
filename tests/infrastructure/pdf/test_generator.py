import asyncio
import shutil
from dataclasses import replace
from datetime import date

import pymupdf
import pytest
from fpdf import FPDF

from esiqie_dictamenes.core.errors import PdfGenerationError
from esiqie_dictamenes.core.paths import project_assets_dir
from esiqie_dictamenes.features.dictamenes.models import (
    Dictamen,
    MateriaElegible,
    PdfRequest,
)
from esiqie_dictamenes.features.dictamenes.pdf import build_session_paragraph
from esiqie_dictamenes.infrastructure.pdf.generator import RealPdfGenerator


REQUIRED_ASSETS = ("ipn_logo.jpg", "logo_esiqie.png", "imagen_fondo.png")
TABLE_HEADERS = (
    "Materia Desfasada",
    "Periodo Reprobada",
    "Intentos Ordinario",
    "Inscrita",
)
LONG_SUBJECT = (
    "PROCESOS DE SEPARACI\u00d3N POR MEMBRANA Y LOS QUE INVOLUCRAN "
    "UNA FASE S\u00d3LIDA"
)
LONG_SUBJECT_MARKERS = ("PROCESOS", "MEMBRANA", "INVOLUCRAN", "S\u00d3LIDA")
TABLE_LEFT_MM = 19
TABLE_RIGHT_MM = 191
FOOTER_TOP_MM = 276
POINTS_PER_MM = 72 / 25.4


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


def _table_request(*materias: MateriaElegible) -> PdfRequest:
    return replace(_request(), materias=materias)


def _extract_text(content: bytes) -> tuple[pymupdf.Document, str]:
    document = pymupdf.open(stream=content, filetype="pdf")
    text = " ".join(
        " ".join(page.get_text().split()) for page in document
    )
    return document, text


def _normalize(value: str) -> str:
    return " ".join(value.split())


def _page_text(page: pymupdf.Page) -> str:
    return " ".join(page.get_text().split())


def _table_bounds_points() -> tuple[float, float, float]:
    return (
        TABLE_LEFT_MM * POINTS_PER_MM,
        TABLE_RIGHT_MM * POINTS_PER_MM,
        FOOTER_TOP_MM * POINTS_PER_MM,
    )


def _find_word_rects(page: pymupdf.Page, token: str) -> list[pymupdf.Rect]:
    return [
        pymupdf.Rect(word[:4])
        for word in page.get_text("words")
        if word[4] == token
    ]


def _subject_page_numbers(document: pymupdf.Document, *tokens: str) -> set[int]:
    pages: set[int] = set()
    for page_number, page in enumerate(document):
        words = {word[4] for word in page.get_text("words")}
        if any(token in words for token in tokens):
            pages.add(page_number)
    return pages


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


def test_generate_renders_the_four_subject_columns_for_one_and_many_subjects():
    request = _table_request(
        MateriaElegible("QUIMICA ORGANICA", 20242, 20, 2, "SI"),
        MateriaElegible("FISICA MODERNA", 20231, 21, 4, "NO"),
        MateriaElegible("TERMODINAMICA APLICADA", 20222, 22, 1, None),
    )

    result = asyncio.run(RealPdfGenerator(project_assets_dir()).generate(request))
    pdf, text = _extract_text(result.content)

    try:
        for header in TABLE_HEADERS:
            assert header in text
        for materia in request.materias:
            assert materia.materia in text
            assert str(materia.periodo_reprobada) in text
            assert str(materia.intentos_ordinario) in text
        assert "SI" in text
        assert "NO" in text
        assert "None" not in text
    finally:
        pdf.close()


def test_generate_wraps_a_long_subject_inside_table_bounds_without_overlapping_next_row():
    request = _table_request(
        MateriaElegible(LONG_SUBJECT, 20242, 20, 3, "SI"),
        MateriaElegible("LABORATORIO DE CINETICA", 20231, 21, 1, "NO"),
    )

    result = asyncio.run(RealPdfGenerator(project_assets_dir()).generate(request))
    pdf = pymupdf.open(stream=result.content, filetype="pdf")

    try:
        page = pdf[0]
        text = _page_text(page)
        left_bound, right_bound, footer_top = _table_bounds_points()
        token_rects = []
        line_positions = set()
        for token in LONG_SUBJECT_MARKERS:
            rects = _find_word_rects(page, token)
            assert rects, f"Missing token {token!r} from long subject row"
            token_rects.extend(rects)
            line_positions.update(round(rect.y0, 1) for rect in rects)

        next_row_rects = _find_word_rects(page, "LABORATORIO")

        assert _normalize(LONG_SUBJECT) in text
        assert len(line_positions) > 1
        assert min(rect.x0 for rect in token_rects) >= left_bound - 3
        assert max(rect.x1 for rect in token_rects) <= right_bound + 3
        assert next_row_rects
        assert max(rect.y1 for rect in token_rects) < min(
            rect.y0 for rect in next_row_rects
        )
        assert max(rect.y1 for rect in token_rects) < footer_top
    finally:
        pdf.close()


def test_generate_repeats_table_headers_on_each_subject_page_without_splitting_rows():
    materias = tuple(
        MateriaElegible(
            (
                f"MATERIA{i:02d} {LONG_SUBJECT} ETAPA{i:02d} "
                f"APLICACION{i:02d} FINAL{i:02d}"
            ),
            20242 - (i % 2),
            20 + i,
            (i % 4) + 1,
            ("SI", "NO", None)[i % 3],
        )
        for i in range(1, 23)
    )
    request = _table_request(*materias)

    result = asyncio.run(RealPdfGenerator(project_assets_dir()).generate(request))
    pdf = pymupdf.open(stream=result.content, filetype="pdf")

    try:
        left_bound, right_bound, footer_top = _table_bounds_points()
        page_texts = [_page_text(page) for page in pdf]
        body_pages = {
            page_number
            for page_number, page_text in enumerate(page_texts)
            if any(f"MATERIA{i:02d}" in page_text for i in range(1, 23))
        }

        assert pdf.page_count > 1
        assert body_pages
        assert sum("ATENTAMENTE" in page_text for page_text in page_texts) == 1
        assert sum("DIRECTOR(A)" in page_text for page_text in page_texts) == 1

        for index, subject in (
            (1, materias[0].materia),
            (10, materias[9].materia),
            (22, materias[-1].materia),
        ):
            normalized_subject = _normalize(subject)
            combined_text = " ".join(page_texts)
            assert combined_text.count(normalized_subject) == 1
            assert _subject_page_numbers(
                pdf,
                f"MATERIA{index:02d}",
                f"ETAPA{index:02d}",
                f"APLICACION{index:02d}",
                f"FINAL{index:02d}",
            ) == {
                next(
                    page_number
                    for page_number, page_text in enumerate(page_texts)
                    if f"MATERIA{index:02d}" in page_text
                )
            }

        for page_number in body_pages:
            page_text = page_texts[page_number]
            for header in TABLE_HEADERS:
                assert header in page_text
            page = pdf[page_number]
            subject_rects = []
            for index in range(1, 23):
                subject_rects.extend(_find_word_rects(page, f"MATERIA{index:02d}"))
            for rect in subject_rects:
                assert rect.x0 >= left_bound - 3
                assert rect.x1 <= right_bound + 3
                assert rect.y1 < footer_top

        signature_rects = []
        for page in pdf:
            signature_rects.extend(page.search_for("ATENTAMENTE"))
            signature_rects.extend(page.search_for("DIRECTOR(A)"))
        assert signature_rects
        assert max(rect.y1 for rect in signature_rects) < footer_top

        last_content_page = max(
            page_number
            for page_number, page_text in enumerate(page_texts)
            if any(
                marker in page_text
                for marker in (
                    "ATENTAMENTE",
                    "DIRECTOR(A)",
                    "MATERIA01",
                    "MATERIA22",
                )
            )
        )
        assert last_content_page == pdf.page_count - 1
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
