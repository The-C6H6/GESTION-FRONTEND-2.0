from enum import StrEnum


class RoutePath(StrEnum):
    LOGIN = "/login"
    DASHBOARD = "/"
    DICTAMENES = "/dictamenes"
    NUEVO_DICTAMEN = "/dictamenes/nuevo"
    ELIMINAR_DICTAMENES = "/dictamenes/eliminar"
    INSCRITOS = "/inscritos"
    NUEVO_USUARIO = "/usuarios/nuevo"


def is_protected_route(path: str | RoutePath) -> bool:
    return str(path) != RoutePath.LOGIN


def is_admin_route(path: str | RoutePath) -> bool:
    return str(path) in {
        RoutePath.ELIMINAR_DICTAMENES,
        RoutePath.NUEVO_USUARIO,
    }
