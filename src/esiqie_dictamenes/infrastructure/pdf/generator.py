import asyncio
from pathlib import Path

from fpdf import FPDF
from fpdf.enums import MethodReturnValue, XPos, YPos

from esiqie_dictamenes.core.errors import PdfGenerationError
from esiqie_dictamenes.features.dictamenes.models import GeneratedDocument, PdfRequest
from esiqie_dictamenes.features.dictamenes.pdf import (
    build_pdf_filename,
    build_session_paragraph,
    format_dictamen_date,
)


_REQUIRED_ASSETS = ("ipn_logo.jpg", "logo_esiqie.png", "imagen_fondo.png")
_BODY_LEFT = 10
_BODY_WIDTH = 190
_BODY_TOP = 83
_TABLE_TOP = 149
_SIGNATURE_TOP = 246
_CONTENT_BOTTOM = 265
_FOOTER_TOP = 269
_TABLE_COLUMNS = (
    ("Materia Desfasada", 112),
    ("Periodo Reprobada", 33),
    ("Intentos Ordinario", 30),
    ("Inscrita", 15),
)
_TABLE_CELL_PADDING_X = 0.2
_TABLE_CELL_PADDING_Y = 0.8
_TABLE_HEADER_MIN_HEIGHT = 10
_TABLE_ROW_MIN_HEIGHT = 8
_TABLE_HEADER_LINE_HEIGHT = 4.2
_TABLE_ROW_LINE_HEIGHT = 4.2


class _InstitutionalPdf(FPDF):
    def __init__(self, assets: dict[str, Path]) -> None:
        super().__init__(orientation="P", unit="mm", format="A4")
        self._assets = assets
        self.set_margins(_BODY_LEFT, _BODY_TOP, _BODY_LEFT)
        self.set_auto_page_break(auto=False)

    def header(self) -> None:
        self.image(str(self._assets["imagen_fondo.png"]), x=30, y=50, w=150)
        self.image(str(self._assets["ipn_logo.jpg"]), x=10, y=10, w=30)
        self.image(str(self._assets["logo_esiqie.png"]), x=180, y=10, w=20)

        self.set_text_color(0, 0, 0)
        self._out("0 g")
        self.set_xy(40, 10)
        self.set_font("Helvetica", "B", 15)
        self.cell(130, 6, "Instituto Politécnico Nacional", align="C")
        self.set_xy(40, 18)
        self.set_font("Helvetica", "", 10)
        for line in (
            "Escuela Superior de Ingeniería Química e Industrias Extractivas",
            "Consejo Técnico Consultivo Escolar",
            "Comisión de Situación Escolar",
        ):
            self.cell(130, 5, line, align="C", new_x=XPos.LEFT, new_y=YPos.NEXT)
            self.set_x(40)
        self.set_xy(40, 34)
        self.set_font("Helvetica", "B", 14)
        self.cell(130, 7, "Dictamen", align="C")
        self.set_xy(_BODY_LEFT, _BODY_TOP)

    def footer(self) -> None:
        self.set_text_color(0, 0, 0)
        self.set_xy(_BODY_LEFT, _FOOTER_TOP)
        self.set_font("Helvetica", "", 7)
        self.multi_cell(
            _BODY_WIDTH,
            3.5,
            "c.c.p. Archivo del Departamento de Gestión Escolar\n"
            "NOTA: Este documento carece de validez oficial si presenta "
            "tachaduras, raspaduras o enmendaduras.",
        )


class RealPdfGenerator:
    def __init__(self, assets_dir: str | Path) -> None:
        self._assets_dir = Path(assets_dir)

    async def generate(self, request: PdfRequest) -> GeneratedDocument:
        try:
            return await asyncio.to_thread(self._generate, request)
        except PdfGenerationError:
            raise
        except Exception:
            raise PdfGenerationError() from None

    def _generate(self, request: PdfRequest) -> GeneratedDocument:
        pdf = _InstitutionalPdf(self._resolve_assets())
        pdf.set_title(f"Dictamen {request.dictamen.clave}")
        pdf.set_author("ESIQIE IPN")
        pdf.add_page()
        self._draw_metadata(pdf, request)
        self._draw_identity(pdf, request)
        self._draw_text_block(
            pdf,
            build_session_paragraph(request.fecha_sesion),
            font_size=8,
            line_height=4,
            align="J",
        )
        pdf.ln(5)
        self._draw_dictaminacion(pdf, request.dictamen.dictaminacion)
        if request.materias:
            pdf.set_y(max(pdf.get_y(), _TABLE_TOP))
            self._draw_subject_table(pdf, request)
        self._draw_signature(
            pdf,
            request.director,
            minimum_y=_SIGNATURE_TOP,
        )

        content = bytes(pdf.output())
        if not content.startswith(b"%PDF-"):
            raise PdfGenerationError()
        return GeneratedDocument(
            filename=build_pdf_filename(request.dictamen),
            content=content,
            is_simulation=False,
        )

    def _resolve_assets(self) -> dict[str, Path]:
        assets = {name: self._assets_dir / name for name in _REQUIRED_ASSETS}
        if not all(path.is_file() for path in assets.values()):
            raise PdfGenerationError()
        return assets

    @staticmethod
    def _draw_metadata(pdf: _InstitutionalPdf, request: PdfRequest) -> None:
        metadata = (
            ("CARÁCTER:", "CONFIDENCIAL"),
            ("PARTES RESERVADAS:", "TODO EL DOCUMENTO"),
            (
                "FUNDAMENTO LEGAL:",
                "ARTÍCULO 3, FRACCIÓN II; ARTÍCULO 18, FRACCIÓN II Y 21 "
                "DE LA LFAIPG, LINEAMIENTO 32°, FRACCIÓN XVII, "
                "LINEAMIENTO 35°.",
            ),
        )
        x = 114
        y = 51
        label_width = 28
        value_width = 58
        for label, value in metadata:
            height = max(
                3,
                RealPdfGenerator._measure_text(
                    pdf, value, width=value_width, font_size=4.5, line_height=2.4
                ),
            )
            pdf.set_xy(x, y)
            pdf.set_font("Helvetica", "B", 4.5)
            pdf.cell(label_width, height, label, align="R")
            pdf.set_xy(x + label_width, y)
            pdf.set_font("Helvetica", "", 4.5)
            pdf.multi_cell(value_width, 2.4, value)
            y += height
        pdf.set_xy(133, max(y + 2, 67))
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(30, 5, "DICTAMEN NO.:", align="R")
        pdf.set_font("Helvetica", "BU", 10)
        pdf.cell(37, 5, request.dictamen.clave)

    @classmethod
    def _draw_identity(cls, pdf: _InstitutionalPdf, request: PdfRequest) -> None:
        pdf.set_xy(_BODY_LEFT, _BODY_TOP)
        pdf.set_font("Helvetica", "", 8)
        pdf.cell(_BODY_WIDTH, 4, format_dictamen_date(request.dictamen.fecha))
        pdf.ln(10)
        cls._draw_labeled_value(pdf, "NOMBRE DEL ALUMNO (A):", request.dictamen.alumno)
        cls._draw_labeled_value(pdf, "NUMERO DE BOLETA:", request.dictamen.boleta)
        pdf.ln(3)

    @classmethod
    def _draw_labeled_value(cls, pdf: _InstitutionalPdf, label: str, value: str) -> None:
        label_width = 43
        value_width = _BODY_WIDTH - label_width
        value_height = cls._measure_text(
            pdf, value, width=value_width, font_style="B", font_size=10, line_height=4.5
        )
        height = max(5, value_height)
        cls._ensure_space(pdf, height + 2)
        x = _BODY_LEFT
        y = pdf.get_y()
        pdf.set_xy(x, y)
        pdf.set_font("Helvetica", "", 8)
        pdf.cell(label_width, height, label)
        pdf.set_xy(x + label_width, y)
        pdf.set_font("Helvetica", "B", 10)
        pdf.multi_cell(value_width, 4.5, value)
        pdf.set_xy(_BODY_LEFT, y + height + 2)

    @classmethod
    def _draw_dictaminacion(cls, pdf: _InstitutionalPdf, text: str) -> None:
        height = cls._measure_text(pdf, text, width=_BODY_WIDTH, font_size=7, line_height=4)
        cls._ensure_space(pdf, height + 2)
        pdf.set_font("Helvetica", "", 7)
        pdf.multi_cell(_BODY_WIDTH, 4, text, border=1)
        pdf.ln(3)

    @classmethod
    def _draw_subject_table(cls, pdf: _InstitutionalPdf, request: PdfRequest) -> None:
        header_height = max(
            _TABLE_HEADER_MIN_HEIGHT,
            cls._measure_table_height(
                pdf,
                tuple(column[0] for column in _TABLE_COLUMNS),
                font_style="B",
                font_size=9,
                line_height=_TABLE_HEADER_LINE_HEIGHT,
            ),
        )
        header_drawn = False
        for index, materia in enumerate(request.materias):
            cells = (
                materia.materia,
                str(materia.periodo_reprobada),
                str(materia.intentos_ordinario),
                materia.materia_inscrita or "",
            )
            row_height = max(_TABLE_ROW_MIN_HEIGHT, cls._measure_table_height(pdf, cells))
            if row_height + header_height > _CONTENT_BOTTOM - _BODY_TOP:
                raise PdfGenerationError()
            required = row_height + (0 if header_drawn else header_height)
            if pdf.get_y() + required > _CONTENT_BOTTOM:
                pdf.add_page()
                header_drawn = False
            if not header_drawn:
                cls._draw_table_header(pdf, header_height)
                header_drawn = True
            cls._draw_table_row(pdf, cells, row_height=row_height, index=index)
        pdf.ln(3)

    @classmethod
    def _draw_table_header(cls, pdf: _InstitutionalPdf, height: float) -> None:
        cls._draw_table_cells(
            pdf,
            tuple(column[0] for column in _TABLE_COLUMNS),
            row_height=height,
            font_style="B",
            font_size=9,
            line_height=_TABLE_HEADER_LINE_HEIGHT,
            fill=(41, 128, 185),
            text_color=(255, 255, 255),
        )

    @classmethod
    def _draw_table_row(
        cls,
        pdf: _InstitutionalPdf,
        cells: tuple[str, str, str, str],
        *,
        row_height: float,
        index: int,
    ) -> None:
        cls._draw_table_cells(
            pdf,
            cells,
            row_height=row_height,
            font_size=8,
            line_height=_TABLE_ROW_LINE_HEIGHT,
            fill=(240, 240, 240) if index % 2 else (255, 255, 255),
            text_color=(0, 0, 0),
        )

    @staticmethod
    def _draw_table_cells(
        pdf: _InstitutionalPdf,
        cells: tuple[str, str, str, str],
        *,
        row_height: float,
        font_size: float,
        line_height: float,
        fill: tuple[int, int, int],
        text_color: tuple[int, int, int],
        font_style: str = "",
    ) -> None:
        x = _BODY_LEFT
        y = pdf.get_y()
        pdf.set_draw_color(0, 0, 0)
        pdf.set_line_width(0.2)
        pdf.set_fill_color(*fill)
        pdf.set_text_color(*text_color)
        for (_, width), value in zip(_TABLE_COLUMNS, cells, strict=True):
            pdf.rect(x, y, width, row_height, style="DF")
            pdf.set_xy(x + _TABLE_CELL_PADDING_X, y + _TABLE_CELL_PADDING_Y)
            pdf.set_font("Helvetica", font_style, font_size)
            pdf.multi_cell(
                width - (_TABLE_CELL_PADDING_X * 2),
                line_height,
                value,
                align="C",
                new_x=XPos.LEFT,
                new_y=YPos.TOP,
            )
            x += width
        pdf.set_text_color(0, 0, 0)
        pdf.set_xy(_BODY_LEFT, y + row_height)

    @classmethod
    def _draw_signature(
        cls,
        pdf: _InstitutionalPdf,
        director: str,
        *,
        minimum_y: float,
    ) -> None:
        signature_height = cls._measure_signature_height(pdf, director)
        target_y = max(pdf.get_y(), minimum_y)
        if target_y + signature_height > _CONTENT_BOTTOM:
            pdf.add_page()
            target_y = pdf.get_y()
            if _SIGNATURE_TOP + signature_height <= _CONTENT_BOTTOM:
                target_y = _SIGNATURE_TOP
        if target_y + signature_height > _CONTENT_BOTTOM:
            raise PdfGenerationError()
        pdf.set_y(target_y)
        cls._draw_text_block(
            pdf, director, font_style="BU", font_size=10, line_height=4.5, align="C"
        )
        pdf.set_x(_BODY_LEFT)
        pdf.set_font("Helvetica", "", 7)
        pdf.multi_cell(
            _BODY_WIDTH,
            3.5,
            "Presidente de la Comisión de Situación Escolar\n"
            "y del Consejo Técnico Consultivo Escolar",
            align="C",
        )

    @classmethod
    def _draw_text_block(
        cls,
        pdf: _InstitutionalPdf,
        text: str,
        *,
        font_size: float,
        line_height: float,
        font_style: str = "",
        align: str = "L",
    ) -> None:
        height = cls._measure_text(
            pdf,
            text,
            width=_BODY_WIDTH,
            font_style=font_style,
            font_size=font_size,
            line_height=line_height,
            align=align,
        )
        cls._ensure_space(pdf, height)
        pdf.set_font("Helvetica", font_style, font_size)
        pdf.multi_cell(_BODY_WIDTH, line_height, text, align=align)

    @staticmethod
    def _measure_text(
        pdf: _InstitutionalPdf,
        text: str,
        *,
        width: float,
        font_size: float,
        line_height: float,
        font_style: str = "",
        align: str = "L",
    ) -> float:
        pdf.set_font("Helvetica", font_style, font_size)
        return pdf.multi_cell(
            width,
            line_height,
            text,
            align=align,
            dry_run=True,
            output=MethodReturnValue.HEIGHT,
        )

    @classmethod
    def _measure_table_height(
        cls,
        pdf: _InstitutionalPdf,
        cells: tuple[str, str, str, str],
        *,
        font_style: str = "",
        font_size: float = 8,
        line_height: float = _TABLE_ROW_LINE_HEIGHT,
    ) -> float:
        return max(
            cls._measure_text(
                pdf,
                value,
                width=width - (_TABLE_CELL_PADDING_X * 2),
                font_style=font_style,
                font_size=font_size,
                line_height=line_height,
                align="C",
            )
            + (_TABLE_CELL_PADDING_Y * 2)
            for (_, width), value in zip(_TABLE_COLUMNS, cells, strict=True)
        )

    @classmethod
    def _measure_signature_height(cls, pdf: _InstitutionalPdf, director: str) -> float:
        director_height = cls._measure_text(
            pdf,
            director,
            width=_BODY_WIDTH,
            font_style="BU",
            font_size=10,
            line_height=4.5,
            align="C",
        )
        return 5 + director_height + 7

    @staticmethod
    def _ensure_space(pdf: _InstitutionalPdf, required_height: float) -> None:
        if required_height > _CONTENT_BOTTOM - _BODY_TOP:
            raise PdfGenerationError()
        if pdf.get_y() + required_height > _CONTENT_BOTTOM:
            pdf.add_page()
