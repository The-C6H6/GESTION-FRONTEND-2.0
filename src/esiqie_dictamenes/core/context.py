from collections.abc import Callable
from dataclasses import dataclass

import flet as ft

from esiqie_dictamenes.core.services import AppServices
from esiqie_dictamenes.features.auth.models import Session


@dataclass(frozen=True)
class AppContextValue:
    services: AppServices
    session: Session | None
    set_session: Callable[[Session | None], None]


AppContext = ft.create_context(None)


def use_app_context() -> AppContextValue:
    context = ft.use_context(AppContext)
    if context is None:
        raise RuntimeError("AppContext is not available.")
    return context
