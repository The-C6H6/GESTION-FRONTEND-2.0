import pytest

from esiqie_dictamenes.core.errors import ConfigurationError
from esiqie_dictamenes.core.settings import load_api_settings


def test_settings_load_api_base_url_and_login_path():
    settings = load_api_settings(
        {
            "API_BASE_URL": "http://api.test",
            "RUTA_LOGIN": "/api/auth/login",
            "RUTA_VISUALIZAR_INSCRITOS": "/api/inscritos/{boleta}",
            "RUTA_REPROBADOS": "/api/reprobados",
            "RUTA_GENERAR_DICTAMEN": "/api/dictaminaciones",
            "RUTA_LECTURA_DICTAMINACIONES": "/api/dictaminaciones",
            "RUTA_MODIFICAR_DICTAMEN": "/api/dictaminaciones/{clave}",
        }
    )

    assert settings.base_url == "http://api.test"
    assert settings.login_path == "/api/auth/login"
    assert settings.inscrito_path == "/api/inscritos/{boleta}"
    assert settings.reprobado_path == "/api/reprobados"
    assert settings.dictamen_create_path == "/api/dictaminaciones"
    assert settings.dictamen_search_path == "/api/dictaminaciones"
    assert settings.dictamen_update_path == "/api/dictaminaciones/{clave}"
    assert settings.timeout_seconds == 10.0


def test_settings_prefer_api_base_url_over_legacy_ip_address():
    settings = load_api_settings(
        {
            "API_BASE_URL": "http://api.test/",
            "IP_ADDRESS": "http://legacy.test",
            "RUTA_LOGIN": "/login",
            "RUTA_VISUALIZAR_INSCRITOS": "/inscritos/{boleta}",
            "RUTA_REPROBADOS": "/reprobados",
            "RUTA_GENERAR_DICTAMEN": "/dictaminaciones",
            "RUTA_LECTURA_DICTAMINACIONES": "/dictaminaciones",
            "RUTA_MODIFICAR_DICTAMEN": "/dictaminaciones/{clave}",
        }
    )

    assert settings.base_url == "http://api.test"


def test_settings_accept_legacy_ip_address():
    settings = load_api_settings(
        {
            "IP_ADDRESS": "http://legacy.test",
            "RUTA_LOGIN": "/login",
            "RUTA_VISUALIZAR_INSCRITOS": "/inscritos/{boleta}",
            "RUTA_REPROBADOS": "/reprobados",
            "RUTA_GENERAR_DICTAMEN": "/dictaminaciones",
            "RUTA_LECTURA_DICTAMINACIONES": "/dictaminaciones",
            "RUTA_MODIFICAR_DICTAMEN": "/dictaminaciones/{clave}",
        }
    )

    assert settings.base_url == "http://legacy.test"


@pytest.mark.parametrize(
    "missing",
    [
        "base_url",
        "login_path",
        "inscrito_path",
        "reprobado_path",
        "dictamen_create_path",
        "dictamen_search_path",
        "dictamen_update_path",
    ],
)
def test_settings_reject_incomplete_configuration(missing):
    keys = {
        "base_url": "API_BASE_URL",
        "login_path": "RUTA_LOGIN",
        "inscrito_path": "RUTA_VISUALIZAR_INSCRITOS",
        "reprobado_path": "RUTA_REPROBADOS",
        "dictamen_create_path": "RUTA_GENERAR_DICTAMEN",
        "dictamen_search_path": "RUTA_LECTURA_DICTAMINACIONES",
        "dictamen_update_path": "RUTA_MODIFICAR_DICTAMEN",
    }
    values = {
        "API_BASE_URL": "http://api.test",
        "RUTA_LOGIN": "/login",
        "RUTA_VISUALIZAR_INSCRITOS": "/inscritos/{boleta}",
        "RUTA_REPROBADOS": "/reprobados",
        "RUTA_GENERAR_DICTAMEN": "/dictaminaciones",
        "RUTA_LECTURA_DICTAMINACIONES": "/dictaminaciones",
        "RUTA_MODIFICAR_DICTAMEN": "/dictaminaciones/{clave}",
    }
    values.pop(keys[missing])

    with pytest.raises(ConfigurationError, match="configuración"):
        load_api_settings(values)


@pytest.mark.parametrize(
    ("values", "message"),
    [
        (
            {
                "API_BASE_URL": "api.test",
                "RUTA_LOGIN": "/login",
                "RUTA_VISUALIZAR_INSCRITOS": "/inscritos/{boleta}",
                "RUTA_REPROBADOS": "/reprobados",
                "RUTA_GENERAR_DICTAMEN": "/dictaminaciones",
                "RUTA_LECTURA_DICTAMINACIONES": "/dictaminaciones",
                "RUTA_MODIFICAR_DICTAMEN": "/dictaminaciones/{clave}",
            },
            "URL base",
        ),
        (
            {
                "API_BASE_URL": "http://api.test",
                "RUTA_LOGIN": "login",
                "RUTA_VISUALIZAR_INSCRITOS": "/inscritos/{boleta}",
                "RUTA_REPROBADOS": "/reprobados",
                "RUTA_GENERAR_DICTAMEN": "/dictaminaciones",
                "RUTA_LECTURA_DICTAMINACIONES": "/dictaminaciones",
                "RUTA_MODIFICAR_DICTAMEN": "/dictaminaciones/{clave}",
            },
            "ruta de login",
        ),
        (
            {
                "API_BASE_URL": "http://api.test",
                "RUTA_LOGIN": "/login",
                "RUTA_VISUALIZAR_INSCRITOS": "/inscritos",
                "RUTA_REPROBADOS": "/reprobados",
                "RUTA_GENERAR_DICTAMEN": "/dictaminaciones",
                "RUTA_LECTURA_DICTAMINACIONES": "/dictaminaciones",
                "RUTA_MODIFICAR_DICTAMEN": "/dictaminaciones/{clave}",
            },
            "ruta de inscritos",
        ),
        (
            {
                "API_BASE_URL": "http://api.test",
                "RUTA_LOGIN": "/login",
                "RUTA_VISUALIZAR_INSCRITOS": "/inscritos/{boleta}",
                "RUTA_REPROBADOS": "/reprobados/{boleta}",
                "RUTA_GENERAR_DICTAMEN": "/dictaminaciones",
                "RUTA_LECTURA_DICTAMINACIONES": "/dictaminaciones",
                "RUTA_MODIFICAR_DICTAMEN": "/dictaminaciones/{clave}",
            },
            "ruta de reprobados",
        ),
        (
            {
                "API_BASE_URL": "http://api.test",
                "RUTA_LOGIN": "/login",
                "RUTA_VISUALIZAR_INSCRITOS": "/inscritos/{boleta}",
                "RUTA_REPROBADOS": "/reprobados?boleta=123",
                "RUTA_GENERAR_DICTAMEN": "/dictaminaciones",
                "RUTA_LECTURA_DICTAMINACIONES": "/dictaminaciones",
                "RUTA_MODIFICAR_DICTAMEN": "/dictaminaciones/{clave}",
            },
            "ruta de reprobados",
        ),
        (
            {
                "API_BASE_URL": "http://api.test",
                "RUTA_LOGIN": "/login",
                "RUTA_VISUALIZAR_INSCRITOS": "/inscritos/{boleta}",
                "RUTA_REPROBADOS": "/reprobados",
                "RUTA_GENERAR_DICTAMEN": "/dictaminaciones?draft=true",
                "RUTA_LECTURA_DICTAMINACIONES": "/dictaminaciones",
                "RUTA_MODIFICAR_DICTAMEN": "/dictaminaciones/{clave}",
            },
            "ruta de creación de dictámenes",
        ),
    ],
)
def test_settings_reject_invalid_urls_and_paths(values, message):
    with pytest.raises(ConfigurationError, match=message):
        load_api_settings(values)


@pytest.mark.parametrize(
    "invalid_path",
    [
        "dictaminaciones",
        "https://api.test/dictaminaciones",
        "/dictaminaciones?boleta=2022630000",
        "/dictaminaciones#results",
        "/dictaminaciones/{boleta}",
    ],
)
def test_settings_reject_invalid_ruling_search_path(invalid_path):
    values = {
        "API_BASE_URL": "http://api.test",
        "RUTA_LOGIN": "/login",
        "RUTA_VISUALIZAR_INSCRITOS": "/inscritos/{boleta}",
        "RUTA_REPROBADOS": "/reprobados",
        "RUTA_GENERAR_DICTAMEN": "/dictaminaciones",
        "RUTA_LECTURA_DICTAMINACIONES": invalid_path,
        "RUTA_MODIFICAR_DICTAMEN": "/dictaminaciones/{clave}",
    }

    with pytest.raises(ConfigurationError, match="ruta de lectura"):
        load_api_settings(values)


@pytest.mark.parametrize(
    "invalid_path",
    [
        "dictaminaciones/{clave}",
        "https://api.test/dictaminaciones/{clave}",
        "/dictaminaciones/{clave}?draft=true",
        "/dictaminaciones/{clave}#edit",
        "/dictaminaciones",
        "/dictaminaciones/{clave}/{clave}",
        "/dictaminaciones/{boleta}",
    ],
)
def test_settings_reject_invalid_ruling_update_path(invalid_path):
    values = {
        "API_BASE_URL": "http://api.test",
        "RUTA_LOGIN": "/login",
        "RUTA_VISUALIZAR_INSCRITOS": "/inscritos/{boleta}",
        "RUTA_REPROBADOS": "/reprobados",
        "RUTA_GENERAR_DICTAMEN": "/dictaminaciones",
        "RUTA_LECTURA_DICTAMINACIONES": "/dictaminaciones",
        "RUTA_MODIFICAR_DICTAMEN": invalid_path,
    }

    with pytest.raises(ConfigurationError, match="ruta de modificaci"):
        load_api_settings(values)
