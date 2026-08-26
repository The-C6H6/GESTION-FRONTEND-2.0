from datetime import date
from urllib.parse import quote

from esiqie_dictamenes.core.errors import BadRequestError, UnexpectedResponseError
from esiqie_dictamenes.features.dictamenes.models import (
    Dictamen,
    DictamenCreate,
    DictamenFilter,
    DictamenPage,
    DictamenUpdate,
)
from esiqie_dictamenes.infrastructure.http.api_client import ApiClient


class ApiDictamenRepository:
    _EMPTY_DETAILS = {
        "no se encontraron dictaminaciones",
        "no se encontraron dictaminaciones con los datos proporcionados",
    }

    def __init__(
        self,
        client: ApiClient,
        create_path: str,
        search_path: str | None = None,
        update_path: str | None = None,
    ) -> None:
        self._client = client
        self._create_path = create_path
        self._search_path = search_path or create_path
        self._update_path = update_path

    async def create(self, payload: DictamenCreate) -> Dictamen:
        response = await self._client.request_json(
            "POST",
            self._create_path,
            json={
                "Boleta": payload.boleta,
                "Nombre": payload.nombre,
                "Fecha": payload.fecha.isoformat(),
                "Anio": payload.anio,
                "Dictaminacion": payload.dictaminacion,
            },
            expected_status=201,
        )
        return self._parse_created(response)

    async def search_page(
        self,
        filters: DictamenFilter,
        *,
        skip: int,
        limit: int,
    ) -> DictamenPage:
        params: dict[str, str | int]
        if filters.boleta is not None:
            params = {"boleta": filters.boleta, "skip": skip, "limit": limit}
        elif filters.anio is not None:
            params = {"anio": filters.anio, "skip": skip, "limit": limit}
        else:
            raise UnexpectedResponseError()
        try:
            response = await self._client.request_json(
                "GET",
                self._search_path,
                params=params,
            )
        except BadRequestError as error:
            if self._is_empty_result(error.detail):
                return DictamenPage(total=0, skip=skip, limit=limit, items=())
            raise
        return self._parse_page(response, expected_skip=skip, expected_limit=limit)

    async def update(self, clave: str, payload: DictamenUpdate) -> Dictamen:
        if self._update_path is None:
            raise UnexpectedResponseError()
        path = self._update_path.format(clave=quote(clave, safe=""))
        response = await self._client.request_json(
            "PUT",
            path,
            json={"Dictaminacion": payload.dictaminacion},
            expected_status=200,
        )
        updated = self._parse_created(response)
        if updated.clave != clave:
            raise UnexpectedResponseError()
        return updated

    @classmethod
    def _is_empty_result(cls, detail: str | None) -> bool:
        if detail is None:
            return False
        return detail.strip().rstrip(".").casefold() in cls._EMPTY_DETAILS

    @classmethod
    def _parse_page(
        cls,
        response: object,
        *,
        expected_skip: int,
        expected_limit: int,
    ) -> DictamenPage:
        if not isinstance(response, dict):
            raise UnexpectedResponseError()
        try:
            total = cls._integer(response, "total")
            skip = cls._integer(response, "skip")
            limit = cls._integer(response, "limit")
            raw_items = response["items"]
            if (
                total < 0
                or skip != expected_skip
                or limit != expected_limit
                or not isinstance(raw_items, list)
                or len(raw_items) > limit
                or len(raw_items) > total
            ):
                raise TypeError("page")
            items = tuple(cls._parse_created(item) for item in raw_items)
            return DictamenPage(total, skip, limit, items)
        except (KeyError, TypeError, ValueError) as error:
            raise UnexpectedResponseError() from error

    @classmethod
    def _parse_created(cls, response: object) -> Dictamen:
        if not isinstance(response, dict):
            raise UnexpectedResponseError()
        try:
            fecha = date.fromisoformat(cls._string(response, "Fecha"))
            return Dictamen(
                clave=cls._string(response, "Clave"),
                boleta=cls._string(response, "Boleta"),
                alumno=cls._string(response, "Nombre"),
                fecha=fecha,
                anio=cls._integer(response, "Anio"),
                dictaminacion=cls._string(response, "Dictaminacion"),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise UnexpectedResponseError() from error

    @staticmethod
    def _string(response: dict, key: str) -> str:
        value = response[key]
        if not isinstance(value, str):
            raise TypeError(key)
        return value

    @staticmethod
    def _integer(response: dict, key: str) -> int:
        value = response[key]
        if type(value) is not int:
            raise TypeError(key)
        return value
