from datetime import date

from esiqie_dictamenes.core.errors import UnexpectedResponseError
from esiqie_dictamenes.features.dictamenes.models import Dictamen, DictamenCreate
from esiqie_dictamenes.infrastructure.http.api_client import ApiClient


class ApiDictamenRepository:
    def __init__(self, client: ApiClient, path: str) -> None:
        self._client = client
        self._path = path

    async def create(self, payload: DictamenCreate) -> Dictamen:
        response = await self._client.request_json(
            "POST",
            self._path,
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
