from esiqie_dictamenes.features.dictamenes.models import GeneratedDocument, PdfRequest
from esiqie_dictamenes.features.dictamenes.pdf import build_session_paragraph


class DemoPdfGenerator:
    async def generate(self, request: PdfRequest) -> GeneratedDocument:
        return GeneratedDocument(
            filename=f"{request.dictamen.boleta}_dictamen.pdf",
            content=b"",
            is_simulation=True,
            preview_text=build_session_paragraph(request.fecha_sesion),
        )
