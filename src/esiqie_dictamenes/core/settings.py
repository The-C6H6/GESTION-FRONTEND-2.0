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
    timeout_seconds: float = 10.0


def load_api_settings(environ: Mapping[str, str] | None = None) -> ApiSettings:
    if environ is None:
        load_dotenv()
        environ = os.environ

    base_url = (environ.get("API_BASE_URL") or environ.get("IP_ADDRESS") or "").strip()
    login_path = (environ.get("RUTA_LOGIN") or "").strip()
    if not base_url or not login_path:
        raise ConfigurationError(
            "La configuración de conexión con la API está incompleta."
        )

    parsed_url = urlsplit(base_url)
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        raise ConfigurationError("La URL base de la API no es válida.")
    if not login_path.startswith("/") or urlsplit(login_path).netloc:
        raise ConfigurationError("La ruta de login de la API no es válida.")

    return ApiSettings(base_url=base_url.rstrip("/"), login_path=login_path)
