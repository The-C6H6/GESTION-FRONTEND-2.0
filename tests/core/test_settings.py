import pytest

from esiqie_dictamenes.core.errors import ConfigurationError
from esiqie_dictamenes.core.settings import ApiSettings, load_api_settings


def valid_environment():
    return {
        "API_BASE_URL": "http://api.test",
        "RUTA_LOGIN": "/api/auth/login",
        "RUTA_NUEVO_USUARIO": "/api/auth/register",
        "RUTA_AUTENTICACION": "/api/auth/me",
        "RUTA_REFRESH": "/api/auth/refresh",
        "RUTA_VISUALIZAR_INSCRITOS": "/api/inscritos/{boleta}",
        "RUTA_REPROBADOS": "/api/reprobados",
        "RUTA_GENERAR_DICTAMEN": "/api/dictaminaciones",
        "RUTA_LECTURA_DICTAMINACIONES": "/api/dictaminaciones",
        "RUTA_MODIFICAR_DICTAMEN": "/api/dictaminaciones/{clave}",
        "RUTA_ELIMINAR": "/api/dictaminaciones/bulk",
    }


def test_settings_repr_excludes_api_url_and_paths():
    settings = ApiSettings(
        base_url="https://private-api.test",
        login_path="/private/login",
        register_path="/private/register",
        auth_me_path="/private/me",
        refresh_path="/private/refresh",
        inscrito_path="/private/inscritos/{boleta}",
        reprobado_path="/private/reprobados",
        dictamen_create_path="/private/dictaminaciones",
        dictamen_search_path="/private/dictaminaciones/search",
        dictamen_update_path="/private/dictaminaciones/{clave}",
        dictamen_delete_path="/private/dictaminaciones/bulk",
    )

    settings_repr = repr(settings)

    assert "https://private-api.test" not in settings_repr
    assert "/private/login" not in settings_repr
    assert "/private/register" not in settings_repr
    assert "/private/me" not in settings_repr
    assert "/private/refresh" not in settings_repr
    assert "/private/inscritos/{boleta}" not in settings_repr
    assert "/private/reprobados" not in settings_repr
    assert "/private/dictaminaciones" not in settings_repr
    assert "/private/dictaminaciones/search" not in settings_repr
    assert "/private/dictaminaciones/{clave}" not in settings_repr
    assert "/private/dictaminaciones/bulk" not in settings_repr
    assert "timeout_seconds=10.0" in settings_repr


def test_settings_load_api_base_url_and_login_path():
    settings = load_api_settings(valid_environment())

    assert settings.base_url == "http://api.test"
    assert settings.login_path == "/api/auth/login"
    assert settings.register_path == "/api/auth/register"
    assert settings.auth_me_path == "/api/auth/me"
    assert settings.refresh_path == "/api/auth/refresh"
    assert settings.inscrito_path == "/api/inscritos/{boleta}"
    assert settings.reprobado_path == "/api/reprobados"
    assert settings.dictamen_create_path == "/api/dictaminaciones"
    assert settings.dictamen_search_path == "/api/dictaminaciones"
    assert settings.dictamen_update_path == "/api/dictaminaciones/{clave}"
    assert settings.dictamen_delete_path == "/api/dictaminaciones/bulk"
    assert settings.timeout_seconds == 10.0


def test_settings_prefer_api_base_url_over_legacy_ip_address():
    values = valid_environment()
    values["API_BASE_URL"] = "http://api.test/"
    values["IP_ADDRESS"] = "http://legacy.test"

    settings = load_api_settings(values)

    assert settings.base_url == "http://api.test"


def test_settings_accept_legacy_ip_address():
    values = valid_environment()
    values.pop("API_BASE_URL")
    values["IP_ADDRESS"] = "http://legacy.test"

    settings = load_api_settings(values)

    assert settings.base_url == "http://legacy.test"


@pytest.mark.parametrize(
    "missing",
    [
        "base_url",
        "login_path",
        "register_path",
        "auth_me_path",
        "refresh_path",
        "inscrito_path",
        "reprobado_path",
        "dictamen_create_path",
        "dictamen_search_path",
        "dictamen_update_path",
        "dictamen_delete_path",
    ],
)
def test_settings_reject_incomplete_configuration(missing):
    keys = {
        "base_url": "API_BASE_URL",
        "login_path": "RUTA_LOGIN",
        "register_path": "RUTA_NUEVO_USUARIO",
        "auth_me_path": "RUTA_AUTENTICACION",
        "refresh_path": "RUTA_REFRESH",
        "inscrito_path": "RUTA_VISUALIZAR_INSCRITOS",
        "reprobado_path": "RUTA_REPROBADOS",
        "dictamen_create_path": "RUTA_GENERAR_DICTAMEN",
        "dictamen_search_path": "RUTA_LECTURA_DICTAMINACIONES",
        "dictamen_update_path": "RUTA_MODIFICAR_DICTAMEN",
        "dictamen_delete_path": "RUTA_ELIMINAR",
    }
    values = valid_environment()
    values.pop(keys[missing])

    with pytest.raises(ConfigurationError, match="configuración"):
        load_api_settings(values)


@pytest.mark.parametrize(
    ("key", "invalid_path"),
    [
        ("RUTA_AUTENTICACION", "api/auth/me"),
        ("RUTA_AUTENTICACION", "https://api.test/api/auth/me"),
        ("RUTA_AUTENTICACION", "/api/auth/me?detail=true"),
        ("RUTA_AUTENTICACION", "/api/auth/{user}"),
        ("RUTA_REFRESH", "api/auth/refresh"),
        ("RUTA_REFRESH", "https://api.test/api/auth/refresh"),
        ("RUTA_REFRESH", "/api/auth/refresh#token"),
        ("RUTA_REFRESH", "/api/auth/{refresh}"),
    ],
)
def test_settings_reject_invalid_authentication_paths(key, invalid_path):
    values = valid_environment()
    values[key] = invalid_path

    with pytest.raises(ConfigurationError, match="autenticaci|renovaci"):
        load_api_settings(values)


@pytest.mark.parametrize(
    "invalid_path",
    [
        "api/auth/register",
        "https://api.test/api/auth/register",
        "/api/auth/register?notify=true",
        "/api/auth/register#form",
        "/api/auth/{username}",
    ],
)
def test_settings_reject_invalid_registration_path(invalid_path):
    values = valid_environment()
    values["RUTA_NUEVO_USUARIO"] = invalid_path

    with pytest.raises(ConfigurationError, match="ruta de registro"):
        load_api_settings(values)


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"API_BASE_URL": "api.test"}, "URL base"),
        ({"RUTA_LOGIN": "login"}, "ruta de login"),
        ({"RUTA_VISUALIZAR_INSCRITOS": "/inscritos"}, "ruta de inscritos"),
        ({"RUTA_REPROBADOS": "/reprobados/{boleta}"}, "ruta de reprobados"),
        ({"RUTA_REPROBADOS": "/reprobados?boleta=123"}, "ruta de reprobados"),
        (
            {"RUTA_GENERAR_DICTAMEN": "/dictaminaciones?draft=true"},
            "ruta de creación de dictámenes",
        ),
    ],
)
def test_settings_reject_invalid_urls_and_paths(override, message):
    values = valid_environment()
    values.update(override)

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
    values = valid_environment()
    values["RUTA_LECTURA_DICTAMINACIONES"] = invalid_path

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
    values = valid_environment()
    values["RUTA_MODIFICAR_DICTAMEN"] = invalid_path

    with pytest.raises(ConfigurationError, match="ruta de modificaci"):
        load_api_settings(values)


@pytest.mark.parametrize(
    "invalid_path",
    [
        "dictaminaciones/bulk",
        "https://api.test/dictaminaciones/bulk",
        "/dictaminaciones/bulk?clave=CSE-0001-26",
        "/dictaminaciones/bulk#delete",
        "/dictaminaciones/{clave}",
    ],
)
def test_settings_reject_invalid_ruling_delete_path(invalid_path):
    values = valid_environment()
    values["RUTA_ELIMINAR"] = invalid_path

    with pytest.raises(ConfigurationError, match="ruta de eliminaci"):
        load_api_settings(values)
