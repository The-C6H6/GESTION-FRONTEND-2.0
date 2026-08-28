from esiqie_dictamenes.core.settings import ApiSettings


def api_settings(**overrides) -> ApiSettings:
    values = {
        "base_url": "http://api.test",
        "login_path": "/api/auth/login",
        "auth_me_path": "/api/auth/me",
        "refresh_path": "/api/auth/refresh",
        "inscrito_path": "/api/inscritos/{boleta}",
        "reprobado_path": "/api/reprobados",
        "dictamen_create_path": "/api/dictaminaciones",
        "dictamen_search_path": "/api/dictaminaciones",
        "dictamen_update_path": "/api/dictaminaciones/{clave}",
        "dictamen_delete_path": "/api/dictaminaciones/bulk",
    }
    values.update(overrides)
    return ApiSettings(**values)
