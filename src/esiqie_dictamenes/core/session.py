from dataclasses import dataclass

from esiqie_dictamenes.features.auth.models import Session


@dataclass
class SessionState:
    current: Session | None = None

    @property
    def is_authenticated(self) -> bool:
        return self.current is not None

    def start(self, session: Session) -> None:
        self.current = session

    def clear(self) -> None:
        self.current = None
