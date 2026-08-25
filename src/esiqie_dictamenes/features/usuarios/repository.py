from typing import Protocol

from esiqie_dictamenes.features.auth.models import RegisteredUser


class UserRepository(Protocol):
    async def register(
        self, username: str, password: str, is_admin: bool
    ) -> RegisteredUser: ...
