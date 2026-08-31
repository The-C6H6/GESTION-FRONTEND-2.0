import asyncio
from collections.abc import Callable
from pathlib import Path
from typing import BinaryIO

from esiqie_dictamenes.core.errors import PdfDestinationError, PdfSaveError


def _write_document(file_handle: BinaryIO, document: bytes) -> None:
    file_handle.write(document)


class LocalPdfDocumentStore:
    def __init__(
        self, writer: Callable[[BinaryIO, bytes], None] = _write_document
    ) -> None:
        self._writer = writer

    def validate_destination(self, destination: str | Path) -> Path:
        target = Path(destination)
        if target.is_dir() or not target.parent.is_dir():
            raise PdfDestinationError()
        if not target.suffix:
            return target.with_suffix(".pdf")
        if target.suffix.lower() != ".pdf":
            raise PdfDestinationError()
        return target

    async def save(self, destination: str | Path, document: bytes) -> Path:
        target = self.validate_destination(destination)
        return await asyncio.to_thread(self._save_exclusively, target, document)

    def _save_exclusively(self, destination: Path, document: bytes) -> Path:
        collision_number = 1
        while True:
            target = self._collision_target(destination, collision_number)
            try:
                file_handle = target.open("xb")
            except FileExistsError:
                collision_number += 1
                continue
            except OSError:
                raise PdfSaveError() from None

            try:
                with file_handle:
                    self._writer(file_handle, document)
            except Exception:
                try:
                    target.unlink()
                except OSError:
                    pass
                raise PdfSaveError() from None

            return target

    @staticmethod
    def _collision_target(destination: Path, collision_number: int) -> Path:
        if collision_number == 1:
            return destination
        return destination.with_name(
            f"{destination.stem}_{collision_number}{destination.suffix}"
        )
