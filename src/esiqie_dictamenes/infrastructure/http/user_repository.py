from datetime import datetime

from esiqie_dictamenes.core.errors import (
    BadRequestError,
    UnexpectedResponseError,
    ValidationError,
)
from esiqie_dictamenes.features.auth.models import RegisteredUser
from esiqie_dictamenes.infrastructure.http.api_client import ApiClient


class ApiUserRepository:
    _DUPLICATE_USERNAME_DETAIL = "el nombre de usuario ya existe"

    def __init__(self, client: ApiClient, register_path: str) -> None:
        self._client = client
        self._register_path = register_path

    async def register(
        self,
        username: str,
        password: str,
        is_admin: bool,
    ) -> RegisteredUser:
        try:
            response = await self._client.request_json(
                "POST",
                self._register_path,
                json={
                    "username": username,
                    "password": password,
                    "is_admin": is_admin,
                },
                expected_status=201,
            )
        except BadRequestError as error:
            if self._is_duplicate_username(error.detail):
                raise ValidationError("El nombre de usuario ya existe.") from error
            raise
        return self._parse_registered_user(
            response,
            expected_username=username,
            expected_is_admin=is_admin,
        )

    @classmethod
    def _is_duplicate_username(cls, detail: str | None) -> bool:
        if detail is None:
            return False
        return detail.strip().rstrip(".").casefold() == cls._DUPLICATE_USERNAME_DETAIL

    @staticmethod
    def _parse_registered_user(
        response: object,
        *,
        expected_username: str,
        expected_is_admin: bool,
    ) -> RegisteredUser:
        if not isinstance(response, dict):
            raise UnexpectedResponseError()
        message = response.get("message")
        created_by = response.get("created_by")
        raw_user = response.get("user")
        if (
            not isinstance(message, str)
            or not message.strip()
            or not isinstance(created_by, str)
            or not created_by.strip()
            or not isinstance(raw_user, dict)
        ):
            raise UnexpectedResponseError()

        user_id = raw_user.get("id")
        username = raw_user.get("username")
        is_active = raw_user.get("is_active")
        is_admin = raw_user.get("is_admin")
        created_at = raw_user.get("created_at")
        if (
            type(user_id) is not int
            or user_id <= 0
            or not isinstance(username, str)
            or username != expected_username
            or type(is_active) is not bool
            or not is_active
            or type(is_admin) is not bool
            or is_admin is not expected_is_admin
            or not isinstance(created_at, str)
            or not created_at.strip()
        ):
            raise UnexpectedResponseError()
        try:
            datetime.fromisoformat(created_at)
        except ValueError as error:
            raise UnexpectedResponseError() from error
        return RegisteredUser(username=username, is_admin=is_admin)
