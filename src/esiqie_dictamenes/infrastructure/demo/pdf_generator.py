from esiqie_dictamenes.features.dictamenes.models import GeneratedDocument, PdfRequest


class DemoPdfGenerator:
    async def generate(self, request: PdfRequest) -> GeneratedDocument:
        return GeneratedDocument(
            filename=f"{request.dictamen.boleta}_dictamen.pdf",
            content=b"",
            is_simulation=True,
        )
