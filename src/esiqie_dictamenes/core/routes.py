from enum import StrEnum


class RoutePath(StrEnum):
    LOGIN = "/login"
    DASHBOARD = "/"
    DICTAMENES = "/dictamenes"
    NUEVO_DICTAMEN = "/dictamenes/nuevo"
    ELIMINAR_DICTAMENES = "/dictamenes/eliminar"
    EDITAR_DICTAMEN = "/dictamenes/:clave/editar"
    INSCRITOS = "/inscritos"
    NUEVO_USUARIO = "/usuarios/nuevo"


def is_protected_route(path: str | RoutePath) -> bool:
    return str(path) != RoutePath.LOGIN
