from collections.abc import Sequence

from esiqie_dictamenes.core.errors import UnexpectedResponseError, ValidationError
from esiqie_dictamenes.features.dictamenes.models import MateriaReprobada
from esiqie_dictamenes.infrastructure.http.api_client import ApiClient


class ApiReprobadoRepository:
    def __init__(self, client: ApiClient, path: str) -> None:
        self._client = client
        self._path = path

    async def search_reprobados(
        self, boleta: str | None = None, nombre: str | None = None
    ) -> Sequence[MateriaReprobada]:
        normalized_boleta = (boleta or "").strip()
        if not normalized_boleta:
            raise ValidationError("Selecciona un alumno con número de boleta.")
        response = await self._client.request_json(
            "GET",
            self._path,
            params={"boleta": normalized_boleta},
        )
        return self._parse_page(response, expected_boleta=normalized_boleta)

    @classmethod
    def _parse_page(
        cls,
        response: object,
        expected_boleta: str,
    ) -> tuple[MateriaReprobada, ...]:
        if not isinstance(response, dict):
            raise UnexpectedResponseError()
        try:
            total = cls._integer(response, "total")
            skip = cls._integer(response, "skip")
            limit = cls._integer(response, "limit")
            items = response["items"]
            if not isinstance(items, list):
                raise TypeError("items")
            if (
                total < 0
                or skip != 0
                or limit < len(items)
                or total != len(items)
            ):
                raise ValueError("partial page")
            return tuple(
                cls._parse_item(item, expected_boleta=expected_boleta)
                for item in items
            )
        except (KeyError, TypeError, ValueError) as error:
            raise UnexpectedResponseError() from error

    @classmethod
    def _parse_item(
        cls,
        item: object,
        expected_boleta: str,
    ) -> MateriaReprobada:
        if not isinstance(item, dict):
            raise TypeError("item")

        boleta = cls._string(item, "Boleta")
        if boleta != expected_boleta:
            raise ValueError("Boleta")
        nombre = cls._string(item, "Nombre")
        cls._string(item, "Turno")
        cls._optional_string(item, "E_Mail_Personal")
        cls._string(item, "Carrera")
        cls._integer(item, "Plan_estud")
        materia = cls._string(item, "Materia")
        cls._string(item, "Departamento")
        cls._string(item, "Academia")
        periodo_reprobada = cls._integer(item, "Periodo_reprobada")
        cls._integer(item, "Intentos_Ordinario")
        cls._optional_integer(item, "Intentos_ETS")
        cls._optional_integer(item, "Total_intentos")
        cls._optional_string(item, "MateriaInscrita")
        cls._optional_string(item, "InscritoActualmente")
        cls._optional_string(item, "Tipo")
        cls._integer(item, "id")

        return MateriaReprobada(
            materia=materia,
            periodo_reprobada=periodo_reprobada,
            boleta=boleta,
            nombre=nombre,
        )

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

    @staticmethod
    def _optional_string(response: dict, key: str) -> str | None:
        value = response[key]
        if value is not None and not isinstance(value, str):
            raise TypeError(key)
        return value

    @staticmethod
    def _optional_integer(response: dict, key: str) -> int | None:
        value = response[key]
        if value is not None and type(value) is not int:
            raise TypeError(key)
        return value
