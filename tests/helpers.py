from esiqie_dictamenes.core.settings import ApiSettings
from esiqie_dictamenes.core.services import AppServices
from esiqie_dictamenes.core.session import AuthSessionStore
from esiqie_dictamenes.features.alumnos.controller import AlumnoController
from esiqie_dictamenes.features.auth.controller import AuthController
from esiqie_dictamenes.features.auth.models import AuthenticatedUser, Session
from esiqie_dictamenes.features.dictamenes.controller import DictamenController
from esiqie_dictamenes.features.usuarios.controller import UserController
from esiqie_dictamenes.infrastructure.demo.alumno_repository import DemoAlumnoRepository
from esiqie_dictamenes.infrastructure.demo.dictamen_repository import (
    DemoDictamenRepository,
)
from esiqie_dictamenes.infrastructure.demo.pdf_generator import DemoPdfGenerator
from esiqie_dictamenes.infrastructure.demo.user_repository import DemoUserRepository


def authenticated_user(*, is_admin: bool = True) -> AuthenticatedUser:
    return AuthenticatedUser(
        id=1,
        username="directivo" if is_admin else "consulta",
        is_active=True,
        is_admin=is_admin,
    )


def authenticated_store(*, is_admin: bool = True) -> AuthSessionStore:
    store = AuthSessionStore()
    store.begin("access-secret", "refresh-secret")
    store.authenticate(authenticated_user(is_admin=is_admin))
    return store


class RejectingLoginRepository:
    async def login(self, username: str, password: str) -> Session:
        raise AssertionError("Test services do not provide demo authentication.")


def build_test_services(*, is_admin: bool = True) -> AppServices:
    login_repository = RejectingLoginRepository()
    user_repository = DemoUserRepository()
    alumno_repository = DemoAlumnoRepository()
    dictamen_repository = DemoDictamenRepository()
    pdf_generator = DemoPdfGenerator()
    auth_session = authenticated_store(is_admin=is_admin)
    return AppServices(
        auth_controller=AuthController(login_repository),
        user_controller=UserController(user_repository, auth_session.require_admin),
        dictamen_controller=DictamenController(
            dictamen_repository,
            alumno_repository,
            pdf_generator,
            require_admin=auth_session.require_admin,
        ),
        alumno_controller=AlumnoController(alumno_repository),
        auth_repository=login_repository,
        dictamen_repository=dictamen_repository,
        auth_session=auth_session,
    )


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
