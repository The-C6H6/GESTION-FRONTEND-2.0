from esiqie_dictamenes.core.errors import (
    AuthenticationError,
    InactiveUserError,
    SessionChangedError,
    SessionExpiredError,
)
from esiqie_dictamenes.core.session import AuthSessionStore
from esiqie_dictamenes.features.auth.models import Session
from esiqie_dictamenes.infrastructure.http.api_client import ApiClient
from esiqie_dictamenes.infrastructure.http.auth_payloads import (
    parse_authenticated_user,
    parse_token_pair,
)


class ApiAuthRepository:
    def __init__(
        self,
        client: ApiClient,
        store: AuthSessionStore,
        login_path: str,
        auth_me_path: str,
    ) -> None:
        self._client = client
        self._store = store
        self._login_path = login_path
        self._auth_me_path = auth_me_path

    async def login(self, username: str, password: str) -> Session:
        self._store.clear()
        pending_session: Session | None = None
        try:
            response = await self._client.request_json(
                "POST",
                self._login_path,
                json={"username": username, "password": password},
                authenticated=False,
                allow_refresh=False,
            )
        except SessionExpiredError as error:
            self._clear_pending_session(pending_session)
            raise AuthenticationError() from error
        except Exception:
            self._clear_pending_session(pending_session)
            raise

        try:
            access_token, refresh_token = parse_token_pair(response)
            if self._store.current is not None:
                raise SessionChangedError()
            pending_session = self._store.begin(access_token, refresh_token)
            identity_response = await self._client.request_json(
                "GET",
                self._auth_me_path,
            )
            if self._store.current is not pending_session:
                raise SessionChangedError()
            user = parse_authenticated_user(identity_response)
            if not user.is_active:
                raise InactiveUserError()
            return self._store.authenticate(user)
        except Exception:
            self._clear_pending_session(pending_session)
            raise

    def _clear_pending_session(self, pending_session: Session | None) -> None:
        if self._store.current is pending_session:
            self._store.clear()
