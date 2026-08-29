from esiqie_dictamenes.core.routes import RoutePath
from esiqie_dictamenes.features.dashboard.view import _dashboard_cards
from tests.helpers import authenticated_user


def test_normal_dashboard_keeps_query_cards_and_read_only_candidate_wording():
    cards = _dashboard_cards(authenticated_user(is_admin=False))

    assert cards == (
        (
            "Buscar dictámenes",
            "Consulta por boleta o año.",
            RoutePath.DICTAMENES,
        ),
        (
            "Consultar alumnos",
            "Consulta alumnos inscritos o con materias reprobadas.",
            RoutePath.NUEVO_DICTAMEN,
        ),
        (
            "Buscar inscrito",
            "Consulta la información académica del alumno.",
            RoutePath.INSCRITOS,
        ),
    )


def test_administrator_dashboard_retains_queries_and_administrative_cards():
    cards = _dashboard_cards(authenticated_user(is_admin=True))

    assert cards == (
        (
            "Buscar dictámenes",
            "Consulta por boleta o año.",
            RoutePath.DICTAMENES,
        ),
        (
            "Nuevo dictamen",
            "Dictamina alumnos inscritos o reprobados.",
            RoutePath.NUEVO_DICTAMEN,
        ),
        (
            "Eliminar dictámenes",
            "Elimina uno o varios dictámenes.",
            RoutePath.ELIMINAR_DICTAMENES,
        ),
        (
            "Buscar inscrito",
            "Consulta la información académica del alumno.",
            RoutePath.INSCRITOS,
        ),
        (
            "Crear usuario",
            "Registra un usuario del sistema.",
            RoutePath.NUEVO_USUARIO,
        ),
    )
