from esiqie_dictamenes.core.errors import AuthorizationError, SessionExpiredError
from esiqie_dictamenes.features.auth.models import AuthenticatedUser, Session


class AuthSessionStore:
    def __init__(self) -> None:
        self._current: Session | None = None

    @property
    def current(self) -> Session | None:
        return self._current

    @property
    def current_user(self) -> AuthenticatedUser | None:
        if self._current is None:
            return None
        return self._current.current_user

    @property
    def access_token(self) -> str | None:
        if self._current is None:
            return None
        return self._current.access_token

    @property
    def refresh_token(self) -> str | None:
        if self._current is None:
            return None
        return self._current.refresh_token

    @property
    def is_authenticated(self) -> bool:
        user = self.current_user
        return user is not None and user.is_active

    def begin(self, access_token: str, refresh_token: str) -> Session:
        self._current = Session(access_token, refresh_token)
        return self._current

    def authenticate(self, user: AuthenticatedUser) -> Session:
        if self._current is None:
            raise SessionExpiredError()
        self._current.authenticated_user = user
        return self._current

    def rotate(self, access_token: str, refresh_token: str) -> None:
        if self._current is None:
            raise SessionExpiredError()
        self._current.access_token = access_token
        self._current.refresh_token = refresh_token

    def clear(self) -> None:
        self._current = None

    def require_admin(self) -> None:
        user = self.current_user
        if user is None or not user.is_active:
            raise SessionExpiredError()
        if not user.is_admin:
            raise AuthorizationError()

    def __repr__(self) -> str:
        return f"AuthSessionStore(is_authenticated={self.is_authenticated})"
