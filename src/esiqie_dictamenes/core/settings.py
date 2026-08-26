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
    if (
        not base_url
        or not login_path
        or not inscrito_path
        or not reprobado_path
        or not dictamen_create_path
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

    return ApiSettings(
        base_url=base_url.rstrip("/"),
        login_path=login_path,
        inscrito_path=inscrito_path,
        reprobado_path=reprobado_path,
        dictamen_create_path=dictamen_create_path,
    )
