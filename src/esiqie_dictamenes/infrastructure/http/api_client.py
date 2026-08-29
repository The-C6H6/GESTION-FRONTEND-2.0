import asyncio
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
from esiqie_dictamenes.infrastructure.http.auth_payloads import (
    parse_token_pair,
)

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
        self._refresh_lock = asyncio.Lock()
        self._refresh_task: asyncio.Task[None] | None = None
        self._refresh_access_token: str | None = None
        self._refresh_waiters = 0

    async def request_json(
        self,
        method: str,
        path: str,
        *,
        json: object | None = None,
        params: Mapping[str, str | int] | None = None,
        expected_status: int | None = None,
        authenticated: bool = True,
        allow_refresh: bool = True,
    ) -> object:
        access_token = self._session.access_token if authenticated else None
        response = await self._send_request(
            method,
            path,
            json=json,
            params=params,
            access_token=access_token,
        )
        if (
            response.status_code == 401
            and authenticated
            and allow_refresh
        ):
            await self._recover_session(access_token)
            response = await self._send_request(
                method,
                path,
                json=json,
                params=params,
                access_token=self._session.access_token,
            )
            if response.status_code == 401:
                self._session.clear()
                raise SessionExpiredError()

        self._raise_for_status(response)
        if (
            expected_status is not None
            and response.status_code != expected_status
        ):
            raise UnexpectedResponseError()
        return self._decode_json(response, method)

    async def _send_request(
        self,
        method: str,
        path: str,
        *,
        json: object | None = None,
        params: Mapping[str, str | int] | None = None,
        access_token: str | None,
    ) -> httpx.Response:
        headers = {"Accept": "application/json"}
        if access_token is not None:
            headers["Authorization"] = f"Bearer {access_token}"

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

        return response

    @staticmethod
    def _decode_json(response: httpx.Response, method: str) -> object:
        try:
            return response.json()
        except ValueError as error:
            logger.warning(
                "API returned invalid JSON: method=%s",
                method,
            )
            raise UnexpectedResponseError() from error

    async def _recover_session(self, failed_access_token: str | None) -> None:
        async with self._refresh_lock:
            current_access_token = self._session.access_token
            if (
                current_access_token is not None
                and current_access_token != failed_access_token
            ):
                return
            if (
                self._refresh_task is not None
                and self._refresh_access_token == failed_access_token
            ):
                refresh_task = self._refresh_task
            else:
                refresh_task = asyncio.create_task(
                    self._perform_refresh(failed_access_token)
                )
                self._refresh_task = refresh_task
                self._refresh_access_token = failed_access_token
                refresh_task.add_done_callback(self._schedule_refresh_cleanup)
            self._refresh_waiters += 1

        try:
            await asyncio.shield(refresh_task)
        finally:
            async with self._refresh_lock:
                self._refresh_waiters -= 1
                if (
                    self._refresh_task is refresh_task
                    and self._refresh_waiters == 0
                    and refresh_task.done()
                ):
                    self._clear_refresh_task()

    async def _perform_refresh(self, failed_access_token: str | None) -> None:
        session = self._session.current
        refresh_token = self._session.refresh_token
        if (
            session is None
            or failed_access_token is None
            or refresh_token is None
            or not refresh_token.strip()
        ):
            self._session.clear()
            raise SessionExpiredError()

        response = await self._send_request(
            "POST",
            self._settings.refresh_path,
            json={"refresh_token": refresh_token},
            access_token=None,
        )
        if response.status_code in {401, 403}:
            self._session.clear()
            raise SessionExpiredError()
        self._raise_for_status(response)
        try:
            access_token, next_refresh_token = parse_token_pair(
                self._decode_json(response, "POST")
            )
        except UnexpectedResponseError:
            self._session.clear()
            raise

        if self._session.current is not session:
            if self._session.current is None:
                raise SessionExpiredError()
            return
        if (
            self._session.access_token != failed_access_token
            or self._session.refresh_token != refresh_token
        ):
            return
        self._session.rotate(access_token, next_refresh_token)

    def _schedule_refresh_cleanup(self, refresh_task: asyncio.Task[None]) -> None:
        if self._refresh_task is refresh_task and self._refresh_waiters == 0:
            asyncio.create_task(self._clear_finished_refresh_task(refresh_task))

    async def _clear_finished_refresh_task(
        self,
        refresh_task: asyncio.Task[None],
    ) -> None:
        async with self._refresh_lock:
            if self._refresh_task is refresh_task and self._refresh_waiters == 0:
                self._clear_refresh_task()
        if not refresh_task.cancelled():
            refresh_task.exception()

    def _clear_refresh_task(self) -> None:
        self._refresh_task = None
        self._refresh_access_token = None

    def _raise_for_status(self, response: httpx.Response) -> None:
        status_code = response.status_code
        if status_code < 400:
            return
        if status_code == 401:
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
