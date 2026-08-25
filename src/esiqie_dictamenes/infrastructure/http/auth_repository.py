from esiqie_dictamenes.core.errors import UnexpectedResponseError
from esiqie_dictamenes.features.auth.models import Session
from esiqie_dictamenes.infrastructure.http.api_client import ApiClient
from esiqie_dictamenes.infrastructure.http.token_store import AuthTokenStore


class ApiAuthRepository:
    def __init__(
        self,
        client: ApiClient,
        tokens: AuthTokenStore,
        login_path: str,
    ) -> None:
        self._client = client
        self._tokens = tokens
        self._login_path = login_path

    async def login(self, username: str, password: str) -> Session:
        self._tokens.clear()
        try:
            response = await self._client.request_json(
                "POST",
                self._login_path,
                json={"username": username, "password": password},
            )
            access_token, refresh_token = self._parse_tokens(response)
            self._tokens.replace(access_token, refresh_token)
        except Exception:
            self._tokens.clear()
            raise

        return Session(username=username, is_admin=False, is_demo=False)

    @staticmethod
    def _parse_tokens(response: object) -> tuple[str, str]:
        if not isinstance(response, dict):
            raise UnexpectedResponseError()
        access_token = response.get("access_token")
        refresh_token = response.get("refresh_token")
        if (
            not isinstance(access_token, str)
            or not access_token.strip()
            or not isinstance(refresh_token, str)
            or not refresh_token.strip()
        ):
            raise UnexpectedResponseError()
        return access_token, refresh_token
