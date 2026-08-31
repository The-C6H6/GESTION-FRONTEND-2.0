import asyncio
from pathlib import Path

from fpdf import FPDF
from fpdf.enums import MethodReturnValue, XPos, YPos

from esiqie_dictamenes.core.errors import PdfGenerationError
from esiqie_dictamenes.features.dictamenes.models import (
    GeneratedDocument,
    PdfRequest,
)
from esiqie_dictamenes.features.dictamenes.pdf import (
    build_pdf_filename,
    build_session_paragraph,
)


_REQUIRED_ASSETS = ("ipn_logo.jpg", "logo_esiqie.png", "imagen_fondo.png")
_PAGE_WIDTH = 210
_PAGE_HEIGHT = 297
_BODY_TOP = 48
_FOOTER_TOP = 276


class _InstitutionalPdf(FPDF):
    def __init__(self, assets: dict[str, Path]) -> None:
        super().__init__(orientation="P", unit="mm", format="A4")
        self._assets = assets
        self.set_margins(19, _BODY_TOP, 19)
        self.set_auto_page_break(auto=True, margin=_PAGE_HEIGHT - _FOOTER_TOP + 3)

    def header(self) -> None:
        self.image(
            str(self._assets["imagen_fondo.png"]),
            x=0,
            y=0,
            w=_PAGE_WIDTH,
            h=_PAGE_HEIGHT,
        )
        self.image(str(self._assets["ipn_logo.jpg"]), x=19, y=10, w=18)
        self.image(str(self._assets["logo_esiqie.png"]), x=170, y=10, w=20)

        self.set_xy(41, 10)
        self.set_font("Helvetica", "B", 10)
        self.multi_cell(
            125,
            4.5,
            "INSTITUTO POLITÉCNICO NACIONAL",
            align="C",
            new_x=XPos.LEFT,
            new_y=YPos.NEXT,
        )
        self.set_x(41)
        self.set_font("Helvetica", "B", 8)
        self.multi_cell(
            125,
            4,
            (
                "ESCUELA SUPERIOR DE INGENIERÍA QUÍMICA E INDUSTRIAS "
                "EXTRACTIVAS"
            ),
            align="C",
            new_x=XPos.LEFT,
            new_y=YPos.NEXT,
        )
        self.set_x(41)
        self.set_font("Helvetica", "", 7.5)
        self.multi_cell(
            125,
            3.8,
            "COMISIÓN DE SITUACIÓN ESCOLAR",
            align="C",
            new_x=XPos.LEFT,
            new_y=YPos.NEXT,
        )
        self.set_y(_BODY_TOP)

    def footer(self) -> None:
        self.set_y(-21)
        self.set_draw_color(92, 16, 55)
        self.set_line_width(0.35)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(2)
        self.set_font("Helvetica", "B", 6.5)
        self.set_text_color(60, 60, 60)
        self.cell(
            0,
            3.5,
            "ESCUELA SUPERIOR DE INGENIERÍA QUÍMICA E INDUSTRIAS EXTRACTIVAS",
            align="C",
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
        )
        self.set_font("Helvetica", "", 6)
        self.cell(
            0,
            3.5,
            "INSTITUTO POLITÉCNICO NACIONAL",
            align="C",
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
        assets = self._resolve_assets()
        pdf = _InstitutionalPdf(assets)
        pdf.set_title(f"Dictamen {request.dictamen.clave}")
        pdf.set_author("Instituto Politécnico Nacional")
        pdf.add_page()

        self._draw_title(pdf)
        self._draw_identity(pdf, request)
        self._draw_wrapped_block(
            pdf,
            build_session_paragraph(request.fecha_sesion),
            font_size=8.5,
            line_height=4.5,
            align="J",
        )
        pdf.ln(2)
        self._draw_dictaminacion(pdf, request.dictamen.dictaminacion)
        self._draw_signature(pdf, request.director)

        content = bytes(pdf.output())
        if not content.startswith(b"%PDF-"):
            raise PdfGenerationError()
        return GeneratedDocument(
            filename=build_pdf_filename(request.dictamen),
            content=content,
            is_simulation=False,
        )

    def _resolve_assets(self) -> dict[str, Path]:
        assets = {
            name: self._assets_dir / name for name in _REQUIRED_ASSETS
        }
        if not all(path.is_file() for path in assets.values()):
            raise PdfGenerationError()
        return assets

    @staticmethod
    def _draw_title(pdf: _InstitutionalPdf) -> None:
        pdf.set_text_color(0, 0, 0)
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(
            0,
            6,
            "DICTAMEN",
            align="C",
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
        )
        pdf.set_font("Helvetica", "B", 7)
        pdf.cell(
            0,
            4,
            "DOCUMENTO CONFIDENCIAL DE USO INSTITUCIONAL",
            align="C",
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
        )
        pdf.ln(2)

    @classmethod
    def _draw_identity(cls, pdf: _InstitutionalPdf, request: PdfRequest) -> None:
        dictamen = request.dictamen
        pdf.set_font("Helvetica", "B", 8.5)
        pdf.cell(86, 5, f"CLAVE: {dictamen.clave}")
        pdf.cell(
            86,
            5,
            f"FECHA: {dictamen.fecha:%d/%m/%Y}",
            align="R",
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
        )
        pdf.ln(1)
        cls._draw_wrapped_block(
            pdf,
            f"ALUMNO: {dictamen.alumno}",
            font_size=9,
            line_height=4.8,
        )
        cls._draw_wrapped_block(
            pdf,
            f"BOLETA: {dictamen.boleta}",
            font_size=9,
            line_height=4.8,
        )
        pdf.ln(2)

    @classmethod
    def _draw_dictaminacion(cls, pdf: _InstitutionalPdf, text: str) -> None:
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(
            0,
            5,
            "DICTAMINACIÓN FINAL",
            align="C",
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
        )
        cls._draw_wrapped_block(
            pdf,
            text,
            font_size=9,
            line_height=5,
            border=1,
            align="J",
        )
        pdf.ln(3)

    @classmethod
    def _draw_signature(cls, pdf: _InstitutionalPdf, director: str) -> None:
        director_height = cls._measure_wrapped_height(
            pdf,
            director,
            font_size=9,
            line_height=4.5,
        )
        required_height = 4 + 4 + 9 + director_height + 4
        available_page_height = pdf.page_break_trigger - pdf.t_margin
        if (
            required_height <= available_page_height
            and required_height > pdf.page_break_trigger - pdf.get_y()
        ):
            pdf.add_page()
        pdf.set_font("Helvetica", "B", 8)
        pdf.cell(
            0,
            4,
            "ATENTAMENTE",
            align="C",
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
        )
        pdf.set_font("Helvetica", "", 7)
        pdf.cell(
            0,
            4,
            '"LA TÉCNICA AL SERVICIO DE LA PATRIA"',
            align="C",
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
        )
        pdf.ln(9)
        cls._draw_wrapped_block(
            pdf,
            director,
            font_size=9,
            line_height=4.5,
            align="C",
        )
        pdf.set_font("Helvetica", "B", 7.5)
        pdf.cell(0, 4, "DIRECTOR(A)", align="C")

    @staticmethod
    def _draw_wrapped_block(
        pdf: _InstitutionalPdf,
        text: str,
        *,
        font_size: float,
        line_height: float,
        border: int = 0,
        align: str = "L",
    ) -> None:
        height = RealPdfGenerator._measure_wrapped_height(
            pdf,
            text,
            font_size=font_size,
            line_height=line_height,
            border=border,
            align=align,
        )
        if height <= pdf.page_break_trigger - pdf.t_margin:
            if height > pdf.page_break_trigger - pdf.get_y():
                pdf.add_page()
        pdf.multi_cell(
            0,
            line_height,
            text,
            border=border,
            align=align,
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
        )

    @staticmethod
    def _measure_wrapped_height(
        pdf: _InstitutionalPdf,
        text: str,
        *,
        font_size: float,
        line_height: float,
        border: int = 0,
        align: str = "L",
    ) -> float:
        pdf.set_font("Helvetica", "", font_size)
        return pdf.multi_cell(
            0,
            line_height,
            text,
            border=border,
            align=align,
            dry_run=True,
            output=MethodReturnValue.HEIGHT,
        )
