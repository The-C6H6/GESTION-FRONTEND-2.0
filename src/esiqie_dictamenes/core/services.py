from dataclasses import dataclass

from esiqie_dictamenes.features.alumnos.controller import AlumnoController
from esiqie_dictamenes.features.auth.controller import AuthController
from esiqie_dictamenes.features.dictamenes.controller import DictamenController
from esiqie_dictamenes.features.usuarios.controller import UserController
from esiqie_dictamenes.infrastructure.demo.alumno_repository import DemoAlumnoRepository
from esiqie_dictamenes.infrastructure.demo.auth_repository import DemoAuthRepository
from esiqie_dictamenes.infrastructure.demo.dictamen_repository import DemoDictamenRepository
from esiqie_dictamenes.infrastructure.demo.pdf_generator import DemoPdfGenerator


@dataclass(frozen=True)
class AppServices:
    auth_controller: AuthController
    user_controller: UserController
    dictamen_controller: DictamenController
    alumno_controller: AlumnoController
    auth_repository: DemoAuthRepository
    dictamen_repository: DemoDictamenRepository


def build_demo_services() -> AppServices:
    auth_repository = DemoAuthRepository()
    alumno_repository = DemoAlumnoRepository()
    dictamen_repository = DemoDictamenRepository()
    pdf_generator = DemoPdfGenerator()
    return AppServices(
        auth_controller=AuthController(auth_repository),
        user_controller=UserController(auth_repository),
        dictamen_controller=DictamenController(
            dictamen_repository, alumno_repository, pdf_generator
        ),
        alumno_controller=AlumnoController(alumno_repository),
        auth_repository=auth_repository,
        dictamen_repository=dictamen_repository,
    )
