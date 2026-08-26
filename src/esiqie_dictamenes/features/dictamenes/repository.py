from collections.abc import Sequence
from typing import Protocol

from .models import (
    Dictamen,
    DictamenCreate,
    DictamenFilter,
    DictamenPage,
    DictamenUpdate,
)


class DictamenCreateRepository(Protocol):
    async def create(self, payload: DictamenCreate) -> Dictamen: ...


class DictamenSearchRepository(Protocol):
    async def search_page(
        self,
        filters: DictamenFilter,
        *,
        skip: int,
        limit: int,
    ) -> DictamenPage: ...


class DictamenUpdateRepository(Protocol):
    async def update(self, clave: str, payload: DictamenUpdate) -> Dictamen: ...


class DictamenRepository(DictamenCreateRepository, Protocol):
    async def search(self, filters: DictamenFilter) -> Sequence[Dictamen]: ...

    async def get(self, clave: str) -> Dictamen: ...

    async def update(self, clave: str, payload: DictamenUpdate) -> Dictamen: ...

    async def delete_many(self, claves: Sequence[str]) -> int: ...
