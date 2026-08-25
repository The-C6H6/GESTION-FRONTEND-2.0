from urllib.parse import quote

from esiqie_dictamenes.core.errors import NotFoundError, UnexpectedResponseError
from esiqie_dictamenes.features.alumnos.models import Inscrito
from esiqie_dictamenes.infrastructure.http.api_client import ApiClient


class ApiInscritoRepository:
    def __init__(self, client: ApiClient, path_template: str) -> None:
        self._client = client
        self._path_template = path_template

    async def get_inscrito(self, boleta: str) -> Inscrito:
        path = self._path_template.replace("{boleta}", quote(boleta, safe=""))
        try:
            response = await self._client.request_json("GET", path)
        except NotFoundError as error:
            raise NotFoundError(
                "No se encontró un alumno inscrito con esa boleta."
            ) from error
        return self._parse_inscrito(response)

    @classmethod
    def _parse_inscrito(cls, response: object) -> Inscrito:
        if not isinstance(response, dict):
            raise UnexpectedResponseError()
        try:
            return Inscrito(
                boleta=cls._string(response, "Boleta"),
                nombre=cls._string(response, "Nombre"),
                carrera=cls._string(response, "Carrera"),
                plan_estud=cls._integer(response, "Plan_estud"),
                especialidad=cls._string(response, "Especialidad"),
                secuencias=cls._string(response, "Secuencias"),
                turno=cls._string(response, "Turno"),
                genero=cls._string(response, "Genero"),
                edad=cls._optional_integer(response, "Edad"),
                promedio=cls._number(response, "Promedio"),
                dictamen_vigente=cls._string(response, "Dictamen_vigente"),
                periodo_escolar_ingreso=cls._string(
                    response, "Periodo_escolar_ingreso"
                ),
                periodos_cursados=cls._integer(response, "Periodos_cursados"),
                semestre_nivel_inscrito=cls._integer(
                    response, "Semestre_Nivel_Inscrito"
                ),
                no_cursadas=cls._integer(response, "No_cursadas"),
                reprobadas=cls._integer(response, "Reprobadas"),
                desfasadas=cls._integer(response, "Desfasadas"),
                periodo_en_que_reprobo=cls._optional_integer(
                    response, "Periodo_en_que_reprobo"
                ),
                materias_inscritas=cls._integer(response, "Materias_inscritas"),
                materias_reprobadas_no_inscritas=cls._optional_integer(
                    response, "Materias_reprobadas_no_inscritas"
                ),
                avance=cls._number(response, "Avance"),
                carga_minima=cls._integer(response, "Carga_minima"),
                carga_media=cls._integer(response, "Carga_media"),
                carga_maxima=cls._integer(response, "Carga_maxima"),
                creditos_inscritos=cls._integer(
                    response, "Total_de_Creditos_inscritos"
                ),
                creditos_de_reprobadas_inscritas=cls._integer(
                    response, "Creditos_de_reprobadas_inscritas"
                ),
                creditos_de_reprobadas_no_inscritas=cls._integer(
                    response, "Creditos_de_reprobadas_no_inscritas"
                ),
                total_de_creditos=cls._integer(response, "Total_de_creditos"),
                posible_irregularidad=cls._optional_string(
                    response, "Posible_irregularidad"
                ),
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

    @staticmethod
    def _optional_integer(response: dict, key: str) -> int | None:
        value = response.get(key)
        if value is not None and type(value) is not int:
            raise TypeError(key)
        return value

    @staticmethod
    def _number(response: dict, key: str) -> float:
        value = response[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(key)
        return float(value)

    @staticmethod
    def _optional_string(response: dict, key: str) -> str | None:
        value = response.get(key)
        if value is not None and not isinstance(value, str):
            raise TypeError(key)
        return value
