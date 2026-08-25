from dataclasses import dataclass

import httpx

from esiqie_dictamenes.core.settings import ApiSettings, load_api_settings
from esiqie_dictamenes.features.alumnos.controller import AlumnoController
from esiqie_dictamenes.features.auth.controller import AuthController
from esiqie_dictamenes.features.auth.repository import LoginRepository
from esiqie_dictamenes.features.dictamenes.controller import DictamenController
from esiqie_dictamenes.features.usuarios.controller import UserController
from esiqie_dictamenes.infrastructure.demo.alumno_repository import DemoAlumnoRepository
from esiqie_dictamenes.infrastructure.demo.auth_repository import DemoAuthRepository
from esiqie_dictamenes.infrastructure.demo.dictamen_repository import DemoDictamenRepository
from esiqie_dictamenes.infrastructure.demo.pdf_generator import DemoPdfGenerator
from esiqie_dictamenes.infrastructure.http.api_client import ApiClient
from esiqie_dictamenes.infrastructure.http.auth_repository import ApiAuthRepository
from esiqie_dictamenes.infrastructure.http.inscrito_repository import (
    ApiInscritoRepository,
)
from esiqie_dictamenes.infrastructure.http.reprobado_repository import (
    ApiReprobadoRepository,
)
from esiqie_dictamenes.infrastructure.http.token_store import AuthTokenStore


@dataclass(frozen=True)
class AppServices:
    auth_controller: AuthController
    user_controller: UserController
    dictamen_controller: DictamenController
    alumno_controller: AlumnoController
    auth_repository: LoginRepository
    dictamen_repository: DemoDictamenRepository
    auth_tokens: AuthTokenStore

    def clear_authentication(self) -> None:
        self.auth_tokens.clear()


def build_demo_services() -> AppServices:
    auth_repository = DemoAuthRepository()
    alumno_repository = DemoAlumnoRepository()
    dictamen_repository = DemoDictamenRepository()
    pdf_generator = DemoPdfGenerator()
    auth_tokens = AuthTokenStore()
    return AppServices(
        auth_controller=AuthController(auth_repository),
        user_controller=UserController(auth_repository),
        dictamen_controller=DictamenController(
            dictamen_repository, alumno_repository, pdf_generator
        ),
        alumno_controller=AlumnoController(alumno_repository),
        auth_repository=auth_repository,
        dictamen_repository=dictamen_repository,
        auth_tokens=auth_tokens,
    )


def build_services(
    settings: ApiSettings | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> AppServices:
    settings = settings or load_api_settings()
    auth_tokens = AuthTokenStore()
    api_client = ApiClient(settings, auth_tokens, transport=transport)
    auth_repository = ApiAuthRepository(
        api_client,
        auth_tokens,
        settings.login_path,
    )
    user_repository = DemoAuthRepository()
    demo_alumno_repository = DemoAlumnoRepository()
    dictamen_repository = DemoDictamenRepository()
    pdf_generator = DemoPdfGenerator()
    inscrito_repository = ApiInscritoRepository(
        api_client,
        settings.inscrito_path,
    )
    reprobado_repository = ApiReprobadoRepository(
        api_client,
        settings.reprobado_path,
    )
    return AppServices(
        auth_controller=AuthController(auth_repository),
        user_controller=UserController(user_repository),
        dictamen_controller=DictamenController(
            dictamen_repository,
            demo_alumno_repository,
            pdf_generator,
            reprobado_repository=reprobado_repository,
        ),
        alumno_controller=AlumnoController(inscrito_repository),
        auth_repository=auth_repository,
        dictamen_repository=dictamen_repository,
        auth_tokens=auth_tokens,
    )
