from esiqie_dictamenes.core.errors import UnexpectedResponseError
from esiqie_dictamenes.features.auth.models import AuthenticatedUser


def parse_token_pair(payload: object) -> tuple[str, str]:
    if not isinstance(payload, dict):
        raise UnexpectedResponseError()
    access_token = payload.get("access_token")
    refresh_token = payload.get("refresh_token")
    if (
        not isinstance(access_token, str)
        or not access_token.strip()
        or not isinstance(refresh_token, str)
        or not refresh_token.strip()
    ):
        raise UnexpectedResponseError()
    return access_token, refresh_token


def parse_authenticated_user(payload: object) -> AuthenticatedUser:
    if not isinstance(payload, dict):
        raise UnexpectedResponseError()
    user_id = payload.get("id")
    username = payload.get("username")
    is_active = payload.get("is_active")
    is_admin = payload.get("is_admin")
    if (
        type(user_id) is not int
        or not isinstance(username, str)
        or not username.strip()
        or type(is_active) is not bool
        or type(is_admin) is not bool
    ):
        raise UnexpectedResponseError()
    return AuthenticatedUser(user_id, username, is_active, is_admin)
