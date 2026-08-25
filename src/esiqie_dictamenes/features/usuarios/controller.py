from esiqie_dictamenes.core.errors import ValidationError
from esiqie_dictamenes.features.auth.models import RegisteredUser

from .repository import UserRepository


class UserController:
    def __init__(self, repository: UserRepository) -> None:
        self._repository = repository

    async def register(
        self,
        username: str,
        password: str,
        password_confirmation: str,
        is_admin: bool,
    ) -> RegisteredUser:
        if not username.strip() or not password:
            raise ValidationError("Usuario y contraseña son obligatorios.")
        if password != password_confirmation:
            raise ValidationError("Las contraseñas no coinciden.")
        return await self._repository.register(username.strip(), password, is_admin)
