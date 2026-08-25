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
        }
    )

    assert settings.base_url == "http://api.test"
    assert settings.login_path == "/api/auth/login"
    assert settings.inscrito_path == "/api/inscritos/{boleta}"
    assert settings.reprobado_path == "/api/reprobados"
    assert settings.timeout_seconds == 10.0


def test_settings_prefer_api_base_url_over_legacy_ip_address():
    settings = load_api_settings(
        {
            "API_BASE_URL": "http://api.test/",
            "IP_ADDRESS": "http://legacy.test",
            "RUTA_LOGIN": "/login",
            "RUTA_VISUALIZAR_INSCRITOS": "/inscritos/{boleta}",
            "RUTA_REPROBADOS": "/reprobados",
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
        }
    )

    assert settings.base_url == "http://legacy.test"


@pytest.mark.parametrize(
    "missing", ["base_url", "login_path", "inscrito_path", "reprobado_path"]
)
def test_settings_reject_incomplete_configuration(missing):
    keys = {
        "base_url": "API_BASE_URL",
        "login_path": "RUTA_LOGIN",
        "inscrito_path": "RUTA_VISUALIZAR_INSCRITOS",
        "reprobado_path": "RUTA_REPROBADOS",
    }
    values = {
        "API_BASE_URL": "http://api.test",
        "RUTA_LOGIN": "/login",
        "RUTA_VISUALIZAR_INSCRITOS": "/inscritos/{boleta}",
        "RUTA_REPROBADOS": "/reprobados",
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
            },
            "URL base",
        ),
        (
            {
                "API_BASE_URL": "http://api.test",
                "RUTA_LOGIN": "login",
                "RUTA_VISUALIZAR_INSCRITOS": "/inscritos/{boleta}",
                "RUTA_REPROBADOS": "/reprobados",
            },
            "ruta de login",
        ),
        (
            {
                "API_BASE_URL": "http://api.test",
                "RUTA_LOGIN": "/login",
                "RUTA_VISUALIZAR_INSCRITOS": "/inscritos",
                "RUTA_REPROBADOS": "/reprobados",
            },
            "ruta de inscritos",
        ),
        (
            {
                "API_BASE_URL": "http://api.test",
                "RUTA_LOGIN": "/login",
                "RUTA_VISUALIZAR_INSCRITOS": "/inscritos/{boleta}",
                "RUTA_REPROBADOS": "/reprobados/{boleta}",
            },
            "ruta de reprobados",
        ),
        (
            {
                "API_BASE_URL": "http://api.test",
                "RUTA_LOGIN": "/login",
                "RUTA_VISUALIZAR_INSCRITOS": "/inscritos/{boleta}",
                "RUTA_REPROBADOS": "/reprobados?boleta=123",
            },
            "ruta de reprobados",
        ),
    ],
)
def test_settings_reject_invalid_urls_and_paths(values, message):
    with pytest.raises(ConfigurationError, match=message):
        load_api_settings(values)
