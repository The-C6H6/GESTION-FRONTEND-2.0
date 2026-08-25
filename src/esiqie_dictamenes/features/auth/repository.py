from typing import Protocol

from .models import Session


class LoginRepository(Protocol):
    async def login(self, username: str, password: str) -> Session: ...
