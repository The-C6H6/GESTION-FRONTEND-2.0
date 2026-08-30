from collections.abc import Callable

from esiqie_dictamenes.core.errors import ValidationError
from esiqie_dictamenes.features.auth.models import RegisteredUser

from .repository import UserRepository


class UserController:
    def __init__(
        self,
        repository: UserRepository,
        require_admin: Callable[[], None],
    ) -> None:
        self._repository = repository
        self._require_admin = require_admin

    async def register(
        self,
        username: str,
        password: str,
        password_confirmation: str,
        is_admin: bool,
    ) -> RegisteredUser:
        self._require_admin()
        if not username.strip() or not password:
            raise ValidationError("Usuario y contraseña son obligatorios.")
        if len(password) < 6:
            raise ValidationError(
                "La contraseña debe tener al menos 6 caracteres."
            )
        if password != password_confirmation:
            raise ValidationError("Las contraseñas no coinciden.")
        return await self._repository.register(username.strip(), password, is_admin)
