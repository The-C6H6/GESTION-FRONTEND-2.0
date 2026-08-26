from collections.abc import Sequence
from typing import Protocol

from .models import Dictamen, DictamenCreate, DictamenFilter, DictamenUpdate


class DictamenCreateRepository(Protocol):
    async def create(self, payload: DictamenCreate) -> Dictamen: ...


class DictamenRepository(DictamenCreateRepository, Protocol):
    async def search(self, filters: DictamenFilter) -> Sequence[Dictamen]: ...

    async def get(self, clave: str) -> Dictamen: ...

    async def update(self, clave: str, payload: DictamenUpdate) -> Dictamen: ...

    async def delete_many(self, claves: Sequence[str]) -> int: ...
