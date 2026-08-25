from esiqie_dictamenes.core.errors import ValidationError

from .models import Session
from .repository import LoginRepository


class AuthController:
    def __init__(self, repository: LoginRepository) -> None:
        self._repository = repository

    async def login(self, username: str, password: str) -> Session:
        if not username.strip() or not password:
            raise ValidationError("Usuario y contraseña son obligatorios.")
        return await self._repository.login(username.strip(), password)
