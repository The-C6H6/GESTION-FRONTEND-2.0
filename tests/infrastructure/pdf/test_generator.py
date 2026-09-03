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
TABLE_COLUMN_WIDTHS_MM = (112, 33, 30, 15)
LONG_SUBJECT = (
    "PROCESOS DE SEPARACI\u00d3N POR MEMBRANA Y LOS QUE INVOLUCRAN "
    "UNA FASE S\u00d3LIDA"
)
LONG_SUBJECT_MARKERS = ("PROCESOS", "MEMBRANA", "INVOLUCRAN", "S\u00d3LIDA")
TABLE_LEFT_MM = 10
TABLE_RIGHT_MM = 200
FOOTER_TOP_MM = 269
POINTS_PER_MM = 72 / 25.4
HISTORICAL_DICTAMEN_TOP_MM = 139
HISTORICAL_TABLE_TOP_MM = 149
HISTORICAL_SIGNATURE_TOP_MM = 240
HISTORICAL_TABLE_HEADER_HEIGHT_MM = 10
HISTORICAL_TABLE_ROW_HEIGHT_MM = 8
BACKGROUND_IMAGE_RECT_MM = (30, 50, 150)
IPN_IMAGE_RECT_MM = (10, 10, 30)
ESIQIE_IMAGE_RECT_MM = (180, 10, 20)
HEADER_BLUE_RGB = (41 / 255, 128 / 255, 185 / 255)
ALTERNATE_ROW_RGB = (240 / 255, 240 / 255, 240 / 255)


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


def _table_rectangles(page: pymupdf.Page) -> list[pymupdf.Rect]:
    rectangles: list[pymupdf.Rect] = []
    left_bound, right_bound, _ = _table_bounds_points()
    for drawing in page.get_drawings():
        rect = drawing.get("rect")
        if rect is None:
            continue
        if rect.x0 < left_bound - 3 or rect.x1 > right_bound + 3:
            continue
        rectangles.append(rect)
    return rectangles


def _table_row_groups(page: pymupdf.Page) -> list[list[pymupdf.Rect]]:
    widths = [width * POINTS_PER_MM for width in TABLE_COLUMN_WIDTHS_MM]
    rows: dict[float, list[pymupdf.Rect]] = {}
    for rect in _table_rectangles(page):
        if not any(abs(rect.width - width) <= 3 for width in widths):
            continue
        rows.setdefault(round(rect.y0, 1), []).append(rect)
    return [
        sorted(rectangles, key=lambda rect: rect.x0)
        for _, rectangles in sorted(rows.items())
        if len(rectangles) == 4
    ]


def _drawing_fill(page: pymupdf.Page, target: pymupdf.Rect) -> tuple[float, float, float]:
    for drawing in page.get_drawings():
        rect = drawing.get("rect")
        if rect is None:
            continue
        if abs(rect.x0 - target.x0) > 0.5 or abs(rect.y0 - target.y0) > 0.5:
            continue
        fill = drawing.get("fill")
        if fill is not None:
            return fill[:3]
    raise AssertionError(f"Missing fill for rectangle {target!r}")


def _image_rectangles(page: pymupdf.Page) -> list[pymupdf.Rect]:
    return [rect for image in page.get_images(full=True) for rect in page.get_image_rects(image[0])]


def _row_rectangles(page: pymupdf.Page, expected_y: float | None = None) -> list[pymupdf.Rect]:
    widths = [width * POINTS_PER_MM for width in TABLE_COLUMN_WIDTHS_MM]
    rectangles = [
        rect
        for rect in _table_rectangles(page)
        if any(abs(rect.width - width) <= 3 for width in widths)
    ]
    if expected_y is None:
        y_positions = sorted({round(rect.y0, 1) for rect in rectangles})
        expected_y = y_positions[-1]
    return [
        rect
        for rect in rectangles
        if abs(rect.y0 - expected_y) <= 1.5
    ]


def _words_inside(page: pymupdf.Page, rect: pymupdf.Rect) -> list[str]:
    words = []
    for word in page.get_text("words"):
        word_rect = pymupdf.Rect(word[:4])
        center_x = (word_rect.x0 + word_rect.x1) / 2
        center_y = (word_rect.y0 + word_rect.y1) / 2
        if rect.contains(pymupdf.Point(center_x, center_y)):
            words.append(word[4])
    return words


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


def test_generate_uses_historical_images_and_short_page_bands():
    request = replace(
        _table_request(MateriaElegible("QUIMICA ORGANICA", 20242, 20, 2, "SI")),
        director="Dra. Ines Munoz",
    )

    result = asyncio.run(RealPdfGenerator(project_assets_dir()).generate(request))
    pdf = pymupdf.open(stream=result.content, filetype="pdf")

    try:
        page = pdf[0]
        image_rectangles = _image_rectangles(page)

        assert len(image_rectangles) == 3

        background = max(image_rectangles, key=lambda rect: rect.width * rect.height)
        ipn_logo = min(image_rectangles, key=lambda rect: rect.x0)
        esiqie_logo = max(image_rectangles, key=lambda rect: rect.x0)

        assert background.x0 == pytest.approx(BACKGROUND_IMAGE_RECT_MM[0] * POINTS_PER_MM, abs=2)
        assert background.y0 == pytest.approx(BACKGROUND_IMAGE_RECT_MM[1] * POINTS_PER_MM, abs=2)
        assert background.width == pytest.approx(BACKGROUND_IMAGE_RECT_MM[2] * POINTS_PER_MM, abs=2)
        assert ipn_logo.x0 == pytest.approx(IPN_IMAGE_RECT_MM[0] * POINTS_PER_MM, abs=2)
        assert ipn_logo.y0 == pytest.approx(IPN_IMAGE_RECT_MM[1] * POINTS_PER_MM, abs=2)
        assert ipn_logo.width == pytest.approx(IPN_IMAGE_RECT_MM[2] * POINTS_PER_MM, abs=2)
        assert esiqie_logo.x0 == pytest.approx(ESIQIE_IMAGE_RECT_MM[0] * POINTS_PER_MM, abs=2)
        assert esiqie_logo.y0 == pytest.approx(ESIQIE_IMAGE_RECT_MM[1] * POINTS_PER_MM, abs=2)
        assert esiqie_logo.width == pytest.approx(ESIQIE_IMAGE_RECT_MM[2] * POINTS_PER_MM, abs=2)

        table_header_rect = page.search_for("Materia")[0]
        signature_rect = page.search_for("Dra.")[0]
        footer_rect = page.search_for("Archivo")[0]

        assert table_header_rect.y0 >= HISTORICAL_TABLE_TOP_MM * POINTS_PER_MM
        assert signature_rect.y0 >= HISTORICAL_SIGNATURE_TOP_MM * POINTS_PER_MM
        assert footer_rect.y0 >= FOOTER_TOP_MM * POINTS_PER_MM - 3
    finally:
        pdf.close()


def test_generate_uses_historical_labels_and_omits_modern_markers():
    request = replace(
        _table_request(MateriaElegible("QUIMICA ORGANICA", 20242, 20, 2, "SI")),
        director="Dra. Ines Munoz",
    )

    result = asyncio.run(RealPdfGenerator(project_assets_dir()).generate(request))
    pdf, text = _extract_text(result.content)

    try:
        assert "NUMERO DE BOLETA:" in _page_text(pdf[0])
        assert "DOCUMENTO CONFIDENCIAL DE USO INSTITUCIONAL" not in text
        assert "ATENTAMENTE" not in text
        assert "DIRECTOR(A)" not in text
        assert "DICTAMINACIÃƒÆ’Ã¢â‚¬Å“N FINAL" not in text
    finally:
        pdf.close()


def test_generate_extracts_historical_accents_in_institutional_copy():
    result = asyncio.run(RealPdfGenerator(project_assets_dir()).generate(_request()))
    pdf, text = _extract_text(result.content)

    try:
        for expected in (
            "Instituto Politécnico Nacional",
            "Escuela Superior de Ingeniería Química e Industrias Extractivas",
            "Consejo Técnico Consultivo Escolar",
            "Comisión de Situación Escolar",
            "CARÁCTER:",
            "ARTÍCULO",
            "FRACCIÓN",
            "32°",
            "Gestión Escolar",
            "Presidente de la Comisión de Situación Escolar",
            "y del Consejo Técnico Consultivo Escolar",
        ):
            assert expected in text
    finally:
        pdf.close()


def test_generate_uses_historical_header_and_alternating_table_fills():
    request = _table_request(
        MateriaElegible("QUIMICA ORGANICA", 20242, 20, 2, "SI"),
        MateriaElegible("FISICA MODERNA", 20231, 21, 4, "NO"),
        MateriaElegible("TERMODINAMICA APLICADA", 20222, 22, 1, None),
    )

    result = asyncio.run(RealPdfGenerator(project_assets_dir()).generate(request))
    pdf = pymupdf.open(stream=result.content, filetype="pdf")

    try:
        rows = _table_row_groups(pdf[0])

        assert len(rows) >= 4
        assert _drawing_fill(pdf[0], rows[0][0]) == pytest.approx(HEADER_BLUE_RGB, abs=0.02)
        assert _drawing_fill(pdf[0], rows[1][0]) == pytest.approx((1.0, 1.0, 1.0), abs=0.02)
        assert _drawing_fill(pdf[0], rows[2][0]) == pytest.approx(ALTERNATE_ROW_RGB, abs=0.02)
        assert _drawing_fill(pdf[0], rows[3][0]) == pytest.approx((1.0, 1.0, 1.0), abs=0.02)
    finally:
        pdf.close()


def test_generate_preserves_historical_minimum_heights_for_short_table_rows():
    request = _table_request(
        MateriaElegible("QUIMICA ORGANICA", 20242, 20, 2, "SI"),
        MateriaElegible("FISICA MODERNA", 20231, 21, 4, "NO"),
    )

    result = asyncio.run(RealPdfGenerator(project_assets_dir()).generate(request))
    pdf = pymupdf.open(stream=result.content, filetype="pdf")

    try:
        rows = _table_row_groups(pdf[0])

        assert rows[0][0].height == pytest.approx(
            HISTORICAL_TABLE_HEADER_HEIGHT_MM * POINTS_PER_MM,
            abs=1,
        )
        assert rows[1][0].height == pytest.approx(
            HISTORICAL_TABLE_ROW_HEIGHT_MM * POINTS_PER_MM,
            abs=1,
        )
        assert rows[2][0].height == pytest.approx(
            HISTORICAL_TABLE_ROW_HEIGHT_MM * POINTS_PER_MM,
            abs=1,
        )
    finally:
        pdf.close()


def test_generate_emits_an_explicit_black_text_state_for_the_first_page_header():
    result = asyncio.run(RealPdfGenerator(project_assets_dir()).generate(_request()))
    pdf = pymupdf.open(stream=result.content, filetype="pdf")

    try:
        stream = b"".join(pdf.xref_stream(xref) for xref in pdf[0].get_contents())
        header_position = stream.index("Instituto Politécnico Nacional".encode("latin-1"))

        assert b"0 g" in stream[:header_position]
    finally:
        pdf.close()


def test_generate_moves_the_signature_up_when_the_subject_table_is_absent():
    without_table = asyncio.run(
        RealPdfGenerator(project_assets_dir()).generate(_request())
    )
    with_table = asyncio.run(
        RealPdfGenerator(project_assets_dir()).generate(
            _table_request(MateriaElegible("QUIMICA ORGANICA", 20242, 20, 2, "SI"))
        )
    )
    no_table_pdf = pymupdf.open(stream=without_table.content, filetype="pdf")
    table_pdf = pymupdf.open(stream=with_table.content, filetype="pdf")

    try:
        no_table_signature = no_table_pdf[0].search_for("Dra.")[0]
        table_signature = table_pdf[0].search_for("Dra.")[0]

        assert no_table_signature.y0 < table_signature.y0
    finally:
        no_table_pdf.close()
        table_pdf.close()


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
                    "DIRECTORA INES",
                    "FIN DE FIRMA",
                    "Presidente de la Comisión",
                )
            )
        }

        assert len(signature_pages) == 1
    finally:
        pdf.close()


def test_generate_never_leaves_a_table_header_without_a_subject_row():
    request = replace(
        _request(),
        materias=(MateriaElegible("QUIMICA ORGANICA", 20242, 20, 2, "SI"),),
        director="DIRECTOR " * 300,
    )

    result = asyncio.run(RealPdfGenerator(project_assets_dir()).generate(request))
    pdf = pymupdf.open(stream=result.content, filetype="pdf")

    try:
        page_texts = [_page_text(page) for page in pdf]
        table_pages = {
            page_number
            for page_number, page_text in enumerate(page_texts)
            if "Materia Desfasada" in page_text
        }
        subject_pages = {
            page_number
            for page_number, page_text in enumerate(page_texts)
            if "QUIMICA ORGANICA" in page_text
        }

        assert table_pages == subject_pages
        assert sum("Presidente de la Comisión de Situación Escolar" in page_text for page_text in page_texts) == 1
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


def test_generate_keeps_the_fourth_cell_empty_but_bordered_when_inscrita_is_none():
    request = _table_request(
        MateriaElegible("SUBJECT-EMPTY-CELL", 20242, 20, 2, None),
    )

    result = asyncio.run(RealPdfGenerator(project_assets_dir()).generate(request))
    pdf = pymupdf.open(stream=result.content, filetype="pdf")

    try:
        page = pdf[0]
        row_rectangles = _row_rectangles(page)

        assert len(row_rectangles) == 4

        fourth_cell = max(row_rectangles, key=lambda rect: rect.x0)
        first_three_words = [_words_inside(page, rect) for rect in sorted(row_rectangles, key=lambda rect: rect.x0)[:3]]

        assert fourth_cell.width == pytest.approx(
            TABLE_COLUMN_WIDTHS_MM[-1] * POINTS_PER_MM,
            abs=3,
        )
        assert _words_inside(page, fourth_cell) == []
        assert any("SUBJECT-EMPTY-CELL" in words for words in first_three_words)
        assert any("20242" in words for words in first_three_words)
        assert any("2" in words for words in first_three_words)
    finally:
        pdf.close()


def test_generate_moves_the_initial_table_header_with_the_first_row_when_space_is_tight():
    request = replace(
        _request(),
        dictamen=replace(
            _request().dictamen,
            dictaminacion="Texto de dictamen largo. " * 117,
        ),
        materias=(
            MateriaElegible("HEADERCHECK01 SUBJECT", 20242, 20, 2, "SI"),
        ),
    )

    result = asyncio.run(RealPdfGenerator(project_assets_dir()).generate(request))
    pdf = pymupdf.open(stream=result.content, filetype="pdf")

    try:
        page_texts = [_page_text(page) for page in pdf]
        header_pages = {
            page_number
            for page_number, page_text in enumerate(page_texts)
            if "Materia Desfasada" in page_text
        }
        subject_pages = _subject_page_numbers(pdf, "HEADERCHECK01")

        assert header_pages == subject_pages
        assert len(header_pages) == 1
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


def test_generate_rejects_a_subject_row_that_cannot_fit_on_one_page():
    request = _table_request(
        MateriaElegible("PALABRA " * 900, 20242, 20, 3, "SI"),
    )

    with pytest.raises(
        PdfGenerationError,
        match=r"^No fue posible generar el documento PDF\.$",
    ):
        asyncio.run(RealPdfGenerator(project_assets_dir()).generate(request))


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
        assert sum("Presidente de la Comisión" in page_text for page_text in page_texts) == 1

        combined_text = " ".join(page_texts)
        for index, subject in enumerate(materias, start=1):
            normalized_subject = _normalize(subject.materia)
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
            signature_rects.extend(page.search_for("Presidente de la Comisión"))
            signature_rects.extend(page.search_for("Dra. Ines"))
        assert signature_rects
        assert max(rect.y1 for rect in signature_rects) < footer_top

        last_content_page = max(
            page_number
            for page_number, page_text in enumerate(page_texts)
            if any(
                marker in page_text
                for marker in (
                    "Presidente de la Comisión",
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
