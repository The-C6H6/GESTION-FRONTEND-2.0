from typing import Protocol

from .models import RegisteredUser, Session


class AuthRepository(Protocol):
    async def login(self, username: str, password: str) -> Session: ...

    async def register(
        self, username: str, password: str, is_admin: bool
    ) -> RegisteredUser: ...
