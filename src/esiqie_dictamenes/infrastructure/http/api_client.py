import logging
from collections.abc import Mapping

import httpx

from esiqie_dictamenes.core.errors import (
    ApiConnectionError,
    ApiTimeoutError,
    AuthorizationError,
    BadRequestError,
    NotFoundError,
    SessionExpiredError,
    ServiceUnavailableError,
    UnexpectedResponseError,
    ValidationError,
)
from esiqie_dictamenes.core.settings import ApiSettings
from esiqie_dictamenes.core.session import AuthSessionStore

logger = logging.getLogger(__name__)


class ApiClient:
    def __init__(
        self,
        settings: ApiSettings,
        session: AuthSessionStore,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._settings = settings
        self._session = session
        self._transport = transport

    async def request_json(
        self,
        method: str,
        path: str,
        *,
        json: object | None = None,
        params: Mapping[str, str | int] | None = None,
        expected_status: int | None = None,
        authenticated: bool = True,
    ) -> object:
        headers = {"Accept": "application/json"}
        if authenticated and self._session.access_token is not None:
            headers["Authorization"] = f"Bearer {self._session.access_token}"

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
                    params=params,
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

        self._raise_for_status(response)
        if expected_status is not None and response.status_code != expected_status:
            raise UnexpectedResponseError()
        try:
            return response.json()
        except ValueError as error:
            logger.warning(
                "API returned invalid JSON: method=%s",
                method,
            )
            raise UnexpectedResponseError() from error

    def _raise_for_status(self, response: httpx.Response) -> None:
        status_code = response.status_code
        if status_code < 400:
            return
        if status_code == 401:
            self._session.clear()
            raise SessionExpiredError()
        if status_code == 400:
            raise BadRequestError(self._safe_error_detail(response))
        if status_code == 403:
            raise AuthorizationError()
        if status_code == 404:
            raise NotFoundError()
        if status_code == 422:
            raise ValidationError()
        if 500 <= status_code < 600:
            raise ServiceUnavailableError()
        raise UnexpectedResponseError()

    @staticmethod
    def _safe_error_detail(response: httpx.Response) -> str | None:
        try:
            payload = response.json()
        except ValueError:
            return None
        if not isinstance(payload, dict):
            return None
        detail = payload.get("detail")
        return detail if isinstance(detail, str) else None
