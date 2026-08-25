import pytest

from esiqie_dictamenes.core.errors import ConfigurationError
from esiqie_dictamenes.core.settings import load_api_settings


def test_settings_load_api_base_url_and_login_path():
    settings = load_api_settings(
        {
            "API_BASE_URL": "http://api.test",
            "RUTA_LOGIN": "/api/auth/login",
            "RUTA_VISUALIZAR_INSCRITOS": "/api/inscritos/{boleta}",
        }
    )

    assert settings.base_url == "http://api.test"
    assert settings.login_path == "/api/auth/login"
    assert settings.inscrito_path == "/api/inscritos/{boleta}"
    assert settings.timeout_seconds == 10.0


def test_settings_prefer_api_base_url_over_legacy_ip_address():
    settings = load_api_settings(
        {
            "API_BASE_URL": "http://api.test/",
            "IP_ADDRESS": "http://legacy.test",
            "RUTA_LOGIN": "/login",
            "RUTA_VISUALIZAR_INSCRITOS": "/inscritos/{boleta}",
        }
    )

    assert settings.base_url == "http://api.test"


def test_settings_accept_legacy_ip_address():
    settings = load_api_settings(
        {
            "IP_ADDRESS": "http://legacy.test",
            "RUTA_LOGIN": "/login",
            "RUTA_VISUALIZAR_INSCRITOS": "/inscritos/{boleta}",
        }
    )

    assert settings.base_url == "http://legacy.test"


@pytest.mark.parametrize("missing", ["base_url", "login_path", "inscrito_path"])
def test_settings_reject_incomplete_configuration(missing):
    keys = {
        "base_url": "API_BASE_URL",
        "login_path": "RUTA_LOGIN",
        "inscrito_path": "RUTA_VISUALIZAR_INSCRITOS",
    }
    values = {
        "API_BASE_URL": "http://api.test",
        "RUTA_LOGIN": "/login",
        "RUTA_VISUALIZAR_INSCRITOS": "/inscritos/{boleta}",
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
            },
            "URL base",
        ),
        (
            {
                "API_BASE_URL": "http://api.test",
                "RUTA_LOGIN": "login",
                "RUTA_VISUALIZAR_INSCRITOS": "/inscritos/{boleta}",
            },
            "ruta de login",
        ),
        (
            {
                "API_BASE_URL": "http://api.test",
                "RUTA_LOGIN": "/login",
                "RUTA_VISUALIZAR_INSCRITOS": "/inscritos",
            },
            "ruta de inscritos",
        ),
    ],
)
def test_settings_reject_invalid_urls_and_paths(values, message):
    with pytest.raises(ConfigurationError, match=message):
        load_api_settings(values)
