from collections.abc import Callable
from dataclasses import dataclass

import flet as ft

from esiqie_dictamenes.core.errors import SessionExpiredError
from esiqie_dictamenes.core.services import AppServices
from esiqie_dictamenes.features.auth.models import Session


@dataclass(frozen=True)
class AppContextValue:
    services: AppServices
    session: Session | None
    set_session: Callable[[Session | None], None]

    def invalidate_session(self) -> None:
        self.services.clear_authentication()
        self.set_session(None)

    def handle_session_error(self, error: Exception) -> bool:
        if not isinstance(error, SessionExpiredError):
            return False
        self.invalidate_session()
        return True


AppContext = ft.create_context(None)


def use_app_context() -> AppContextValue:
    context = ft.use_context(AppContext)
    if context is None:
        raise RuntimeError("AppContext is not available.")
    return context
