"""Small adapters for selecting and reporting locally generated PDFs."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import flet as ft

from esiqie_dictamenes.features.dictamenes.models import Dictamen
from esiqie_dictamenes.features.dictamenes.pdf import build_pdf_filename


_DESKTOP_PLATFORMS = frozenset({"windows", "macos", "linux"})


def platform_supports_pdf_output(*, web: bool, platform: Any) -> bool:
    """Return whether a platform can choose a local destination before POST."""
    if web:
        return False
    value = getattr(platform, "value", platform)
    return value in _DESKTOP_PLATFORMS


def require_desktop_pdf_output(page: Any) -> None:
    """Reject platforms where Flet cannot return a path before writing bytes."""
    if not platform_supports_pdf_output(
        web=bool(getattr(page, "web", False)),
        platform=getattr(page, "platform", None),
    ):
        raise ValueError(
            "La generaci\u00f3n y guardado de PDF est\u00e1 disponible "
            "\u00fanicamente en la aplicaci\u00f3n de escritorio."
        )


class FletPdfDestinationSelector:
    """Use one memoized Flet FilePicker service for desktop save dialogs."""

    def __init__(self, picker: Any) -> None:
        self._picker = picker

    async def select(self, dictamen: Dictamen) -> str | None:
        return await self._picker.save_file(
            file_name=build_pdf_filename(dictamen),
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=["pdf"],
        )


def use_file_picker() -> Any:
    """Create a stable FilePicker service for a Flet component instance."""
    return ft.use_memo(ft.FilePicker, [])


@dataclass(frozen=True)
class CreatePdfResult:
    """Outcome of a staged create plus PDF output workflow."""

    dictamen: Dictamen | None
    saved_path: Path | str | None = None
    cancelled: bool = False
    pdf_saved: bool = False
    message: str = ""


@dataclass(frozen=True)
class UpdatePdfResult:
    """Outcome of a staged update plus PDF output workflow."""

    updated: Dictamen | None
    saved_path: Path | str | None = None
    cancelled: bool = False
    no_op: bool = False
    pdf_saved: bool = False
    message: str = ""


def selector_result(selector: Any, dictamen: Dictamen) -> Any:
    """Return a selector result while allowing simple recording test doubles."""
    if hasattr(selector, "select"):
        return selector.select(dictamen)
    return selector(dictamen)


def post_mutation_pdf_failure_message(clave: str) -> str:
    return (
        f"Dictamen creado correctamente. Clave: {clave}. "
        "El PDF no se pudo guardar; conserva esta clave y verifica el "
        "dictamen antes de intentar cualquier otra acci\u00f3n."
    )


def saved_pdf_message(clave: str, path: Path | str) -> str:
    return (
        f"Dictamen creado correctamente. Clave: {clave}. "
        f"PDF guardado en: {path}"
    )


def post_update_pdf_failure_message(
    clave: str,
    destination: Path | str | None = None,
) -> str:
    suffix = f" Ruta seleccionada: {destination}." if destination else ""
    return (
        f"Dictamen actualizado correctamente. Clave: {clave}. "
        "El PDF no se pudo guardar; verifica el dictamen antes de intentar "
        f"cualquier otra acci\u00f3n.{suffix}"
    )


def updated_pdf_message(clave: str, path: Path | str) -> str:
    return (
        f"Dictamen actualizado correctamente. Clave: {clave}. "
        f"PDF guardado en: {path}"
    )
