import os
from collections.abc import Mapping
from dataclasses import dataclass
from urllib.parse import urlsplit

from dotenv import load_dotenv

from esiqie_dictamenes.core.errors import ConfigurationError


@dataclass(frozen=True)
class ApiSettings:
    base_url: str
    login_path: str
    inscrito_path: str
    reprobado_path: str
    dictamen_create_path: str
    dictamen_search_path: str
    dictamen_update_path: str
    dictamen_delete_path: str
    timeout_seconds: float = 10.0


def load_api_settings(environ: Mapping[str, str] | None = None) -> ApiSettings:
    if environ is None:
        load_dotenv()
        environ = os.environ

    base_url = (environ.get("API_BASE_URL") or environ.get("IP_ADDRESS") or "").strip()
    login_path = (environ.get("RUTA_LOGIN") or "").strip()
    inscrito_path = (environ.get("RUTA_VISUALIZAR_INSCRITOS") or "").strip()
    reprobado_path = (environ.get("RUTA_REPROBADOS") or "").strip()
    dictamen_create_path = (environ.get("RUTA_GENERAR_DICTAMEN") or "").strip()
    dictamen_search_path = (
        environ.get("RUTA_LECTURA_DICTAMINACIONES") or ""
    ).strip()
    dictamen_update_path = (
        environ.get("RUTA_MODIFICAR_DICTAMEN") or ""
    ).strip()
    dictamen_delete_path = (environ.get("RUTA_ELIMINAR") or "").strip()
    if (
        not base_url
        or not login_path
        or not inscrito_path
        or not reprobado_path
        or not dictamen_create_path
        or not dictamen_search_path
        or not dictamen_update_path
        or not dictamen_delete_path
    ):
        raise ConfigurationError(
            "La configuración de conexión con la API está incompleta."
        )

    parsed_url = urlsplit(base_url)
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        raise ConfigurationError("La URL base de la API no es válida.")
    if not login_path.startswith("/") or urlsplit(login_path).netloc:
        raise ConfigurationError("La ruta de login de la API no es válida.")
    if (
        not inscrito_path.startswith("/")
        or urlsplit(inscrito_path).netloc
        or inscrito_path.count("{boleta}") != 1
    ):
        raise ConfigurationError("La ruta de inscritos de la API no es válida.")
    parsed_reprobado_path = urlsplit(reprobado_path)
    if (
        not reprobado_path.startswith("/")
        or parsed_reprobado_path.netloc
        or parsed_reprobado_path.query
        or parsed_reprobado_path.fragment
        or "{" in reprobado_path
        or "}" in reprobado_path
    ):
        raise ConfigurationError("La ruta de reprobados de la API no es válida.")
    parsed_dictamen_create_path = urlsplit(dictamen_create_path)
    if (
        not dictamen_create_path.startswith("/")
        or parsed_dictamen_create_path.netloc
        or parsed_dictamen_create_path.query
        or parsed_dictamen_create_path.fragment
        or "{" in dictamen_create_path
        or "}" in dictamen_create_path
    ):
        raise ConfigurationError(
            "La ruta de creación de dictámenes de la API no es válida."
        )
    parsed_dictamen_search_path = urlsplit(dictamen_search_path)
    if (
        not dictamen_search_path.startswith("/")
        or parsed_dictamen_search_path.netloc
        or parsed_dictamen_search_path.query
        or parsed_dictamen_search_path.fragment
        or "{" in dictamen_search_path
        or "}" in dictamen_search_path
    ):
        raise ConfigurationError(
            "La ruta de lectura de dictámenes de la API no es válida."
        )
    parsed_dictamen_update_path = urlsplit(dictamen_update_path)
    if (
        not dictamen_update_path.startswith("/")
        or parsed_dictamen_update_path.netloc
        or parsed_dictamen_update_path.query
        or parsed_dictamen_update_path.fragment
        or dictamen_update_path.count("{clave}") != 1
        or dictamen_update_path.count("{") != 1
        or dictamen_update_path.count("}") != 1
    ):
        raise ConfigurationError(
            "La ruta de modificación de dictámenes de la API no es válida."
        )
    parsed_dictamen_delete_path = urlsplit(dictamen_delete_path)
    if (
        not dictamen_delete_path.startswith("/")
        or parsed_dictamen_delete_path.netloc
        or parsed_dictamen_delete_path.query
        or parsed_dictamen_delete_path.fragment
        or "{" in dictamen_delete_path
        or "}" in dictamen_delete_path
    ):
        raise ConfigurationError(
            "La ruta de eliminación de dictámenes de la API no es válida."
        )

    return ApiSettings(
        base_url=base_url.rstrip("/"),
        login_path=login_path,
        inscrito_path=inscrito_path,
        reprobado_path=reprobado_path,
        dictamen_create_path=dictamen_create_path,
        dictamen_search_path=dictamen_search_path,
        dictamen_update_path=dictamen_update_path,
        dictamen_delete_path=dictamen_delete_path,
    )
