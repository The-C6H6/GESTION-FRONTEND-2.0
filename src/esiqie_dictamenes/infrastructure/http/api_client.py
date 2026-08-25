import logging

import httpx

from esiqie_dictamenes.core.errors import (
    ApiConnectionError,
    ApiTimeoutError,
    AuthorizationError,
    NotFoundError,
    SessionExpiredError,
    ServiceUnavailableError,
    UnexpectedResponseError,
    ValidationError,
)
from esiqie_dictamenes.core.settings import ApiSettings
from esiqie_dictamenes.infrastructure.http.token_store import AuthTokenStore

logger = logging.getLogger(__name__)


class ApiClient:
    def __init__(
        self,
        settings: ApiSettings,
        tokens: AuthTokenStore,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._settings = settings
        self._tokens = tokens
        self._transport = transport

    async def request_json(
        self,
        method: str,
        path: str,
        *,
        json: object | None = None,
    ) -> object:
        headers = {"Accept": "application/json"}
        if self._tokens.access_token is not None:
            headers["Authorization"] = f"Bearer {self._tokens.access_token}"

        try:
            async with httpx.AsyncClient(
                base_url=self._settings.base_url,
                timeout=self._settings.timeout_seconds,
                transport=self._transport,
            ) as client:
                response = await client.request(
                    method,
                    path,
                    json=json,
                    headers=headers,
                )
        except httpx.TimeoutException as error:
            logger.warning(
                "API request timed out: method=%s error=%s",
                method,
                type(error).__name__,
            )
            raise ApiTimeoutError() from error
        except httpx.RequestError as error:
            logger.warning(
                "API request failed: method=%s error=%s",
                method,
                type(error).__name__,
            )
            raise ApiConnectionError() from error

        self._raise_for_status(response.status_code)
        try:
            return response.json()
        except ValueError as error:
            logger.warning(
                "API returned invalid JSON: method=%s",
                method,
            )
            raise UnexpectedResponseError() from error

    def _raise_for_status(self, status_code: int) -> None:
        if status_code < 400:
            return
        if status_code == 401:
            self._tokens.clear()
            raise SessionExpiredError()
        if status_code == 403:
            raise AuthorizationError()
        if status_code == 404:
            raise NotFoundError()
        if status_code == 422:
            raise ValidationError()
        if 500 <= status_code < 600:
            raise ServiceUnavailableError()
        raise UnexpectedResponseError()
