import asyncio
import logging
from collections.abc import Mapping
from dataclasses import dataclass

import httpx

from esiqie_dictamenes.core.errors import (
    ApiConnectionError,
    ApiTimeoutError,
    AuthorizationError,
    BadRequestError,
    NotFoundError,
    SessionChangedError,
    SessionExpiredError,
    ServiceUnavailableError,
    UnexpectedResponseError,
    ValidationError,
)
from esiqie_dictamenes.core.settings import ApiSettings
from esiqie_dictamenes.core.session import AuthSessionStore
from esiqie_dictamenes.features.auth.models import Session
from esiqie_dictamenes.infrastructure.http.auth_payloads import (
    parse_token_pair,
)

logger = logging.getLogger(__name__)


@dataclass
class _RefreshFlight:
    session: Session
    failed_access_token: str
    task: asyncio.Task[str]
    waiters: int = 0


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
        self._refresh_flights: list[_RefreshFlight] = []

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
        origin_session = self._session.current if authenticated else None
        access_token = (
            origin_session.access_token if origin_session is not None else None
        )
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
            replay_access_token = await self._recover_session(
                origin_session,
                access_token,
            )
            response = await self._send_request(
                method,
                path,
                json=json,
                params=params,
                access_token=replay_access_token,
            )
            self._require_session_ownership(
                origin_session,
                replay_access_token,
            )
            if response.status_code == 401:
                if self._clear_owned_session(
                    origin_session,
                    replay_access_token,
                ):
                    raise SessionExpiredError()
                raise SessionChangedError()

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

    async def _recover_session(
        self,
        origin_session: Session | None,
        failed_access_token: str | None,
    ) -> str:
        if origin_session is None or failed_access_token is None:
            if self._session.current is origin_session:
                self._session.clear()
                raise SessionExpiredError()
            raise SessionChangedError()

        async with self._refresh_lock:
            if self._session.current is not origin_session:
                raise SessionChangedError()
            if origin_session.access_token != failed_access_token:
                return origin_session.access_token

            flight = self._find_refresh_flight(
                origin_session,
                failed_access_token,
            )
            if flight is not None and flight.waiters == 0 and flight.task.done():
                self._remove_refresh_flight(flight)
                flight = None
            if flight is None:
                refresh_task = asyncio.create_task(
                    self._perform_refresh(origin_session, failed_access_token)
                )
                flight = _RefreshFlight(
                    origin_session,
                    failed_access_token,
                    refresh_task,
                )
                self._refresh_flights.append(flight)
                refresh_task.add_done_callback(
                    lambda _task, refresh_flight=flight: (
                        self._schedule_refresh_cleanup(refresh_flight)
                    )
                )
            flight.waiters += 1

        try:
            replay_access_token = await asyncio.shield(flight.task)
        finally:
            async with self._refresh_lock:
                flight.waiters -= 1
                if flight.waiters == 0 and flight.task.done():
                    self._remove_refresh_flight(flight)

        self._require_session_ownership(
            origin_session,
            replay_access_token,
        )
        return replay_access_token

    async def _perform_refresh(
        self,
        origin_session: Session,
        failed_access_token: str,
    ) -> str:
        self._require_session_ownership(
            origin_session,
            failed_access_token,
        )
        refresh_token = origin_session.refresh_token
        if not refresh_token.strip():
            if self._clear_owned_session(
                origin_session,
                failed_access_token,
            ):
                raise SessionExpiredError()
            raise SessionChangedError()

        try:
            response = await self._send_request(
                "POST",
                self._settings.refresh_path,
                json={"refresh_token": refresh_token},
                access_token=None,
            )
        except (ApiConnectionError, ApiTimeoutError) as error:
            try:
                self._require_session_ownership(
                    origin_session,
                    failed_access_token,
                    refresh_token,
                )
            except SessionChangedError as changed_error:
                raise changed_error from error
            raise

        self._require_session_ownership(
            origin_session,
            failed_access_token,
            refresh_token,
        )
        if response.status_code in {401, 403}:
            if self._clear_owned_session(
                origin_session,
                failed_access_token,
                refresh_token,
            ):
                raise SessionExpiredError()
            raise SessionChangedError()
        self._raise_for_status(response)
        try:
            access_token, next_refresh_token = parse_token_pair(
                self._decode_json(response, "POST")
            )
        except UnexpectedResponseError:
            if not self._clear_owned_session(
                origin_session,
                failed_access_token,
                refresh_token,
            ):
                raise SessionChangedError()
            raise

        self._require_session_ownership(
            origin_session,
            failed_access_token,
            refresh_token,
        )
        self._session.rotate(access_token, next_refresh_token)
        return access_token

    def _find_refresh_flight(
        self,
        origin_session: Session,
        failed_access_token: str,
    ) -> _RefreshFlight | None:
        for flight in self._refresh_flights:
            if (
                flight.session is origin_session
                and flight.failed_access_token == failed_access_token
            ):
                return flight
        return None

    def _schedule_refresh_cleanup(self, flight: _RefreshFlight) -> None:
        if flight.waiters == 0 and self._has_refresh_flight(flight):
            asyncio.create_task(self._clear_finished_refresh_flight(flight))

    async def _clear_finished_refresh_flight(
        self,
        flight: _RefreshFlight,
    ) -> None:
        async with self._refresh_lock:
            if flight.waiters == 0:
                self._remove_refresh_flight(flight)
        if not flight.task.cancelled():
            flight.task.exception()

    def _has_refresh_flight(self, flight: _RefreshFlight) -> bool:
        return any(active is flight for active in self._refresh_flights)

    def _remove_refresh_flight(self, flight: _RefreshFlight) -> None:
        self._refresh_flights = [
            active for active in self._refresh_flights if active is not flight
        ]

    def _require_session_ownership(
        self,
        origin_session: Session | None,
        access_token: str,
        refresh_token: str | None = None,
    ) -> None:
        if (
            origin_session is None
            or self._session.current is not origin_session
            or origin_session.access_token != access_token
            or (
                refresh_token is not None
                and origin_session.refresh_token != refresh_token
            )
        ):
            raise SessionChangedError()

    def _clear_owned_session(
        self,
        origin_session: Session | None,
        access_token: str,
        refresh_token: str | None = None,
    ) -> bool:
        try:
            self._require_session_ownership(
                origin_session,
                access_token,
                refresh_token,
            )
        except SessionChangedError:
            return False
        self._session.clear()
        return True

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
