from typing import Protocol

from .models import GeneratedDocument, PdfRequest


class PdfGenerator(Protocol):
    async def generate(self, request: PdfRequest) -> GeneratedDocument: ...
