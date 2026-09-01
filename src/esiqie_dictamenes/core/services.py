from dataclasses import dataclass

import httpx

from esiqie_dictamenes.core.paths import project_assets_dir
from esiqie_dictamenes.core.settings import ApiSettings, load_api_settings
from esiqie_dictamenes.core.session import AuthSessionStore
from esiqie_dictamenes.features.alumnos.controller import AlumnoController
from esiqie_dictamenes.features.auth.controller import AuthController
from esiqie_dictamenes.features.auth.repository import LoginRepository
from esiqie_dictamenes.features.dictamenes.controller import DictamenController
from esiqie_dictamenes.features.dictamenes.pdf import PdfDocumentStore
from esiqie_dictamenes.features.dictamenes.repository import DictamenRepository
from esiqie_dictamenes.features.usuarios.controller import UserController
from esiqie_dictamenes.infrastructure.demo.alumno_repository import DemoAlumnoRepository
from esiqie_dictamenes.infrastructure.http.api_client import ApiClient
from esiqie_dictamenes.infrastructure.http.auth_repository import ApiAuthRepository
from esiqie_dictamenes.infrastructure.http.dictamen_repository import (
    ApiDictamenRepository,
)
from esiqie_dictamenes.infrastructure.http.inscrito_repository import (
    ApiInscritoRepository,
)
from esiqie_dictamenes.infrastructure.http.reprobado_repository import (
    ApiReprobadoRepository,
)
from esiqie_dictamenes.infrastructure.http.user_repository import ApiUserRepository
from esiqie_dictamenes.infrastructure.pdf.document_store import LocalPdfDocumentStore
from esiqie_dictamenes.infrastructure.pdf.generator import RealPdfGenerator


@dataclass(frozen=True)
class AppServices:
    auth_controller: AuthController
    user_controller: UserController
    dictamen_controller: DictamenController
    alumno_controller: AlumnoController
    auth_repository: LoginRepository
    dictamen_repository: DictamenRepository
    auth_session: AuthSessionStore
    document_store: PdfDocumentStore

    def clear_authentication(self) -> None:
        self.auth_session.clear()


def build_services(
    settings: ApiSettings | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> AppServices:
    settings = settings or load_api_settings()
    auth_session = AuthSessionStore()
    api_client = ApiClient(settings, auth_session, transport=transport)
    auth_repository = ApiAuthRepository(
        api_client,
        auth_session,
        settings.login_path,
        settings.auth_me_path,
    )
    user_repository = ApiUserRepository(api_client, settings.register_path)
    inscrito_repository = ApiInscritoRepository(
        api_client,
        settings.inscrito_path,
    )
    reprobado_repository = ApiReprobadoRepository(
        api_client,
        settings.reprobado_path,
    )
    dictamen_repository = ApiDictamenRepository(
        api_client,
        settings.dictamen_create_path,
        settings.dictamen_search_path,
        settings.dictamen_update_path,
        settings.dictamen_delete_path,
    )
    pdf_generator = RealPdfGenerator(project_assets_dir())
    document_store = LocalPdfDocumentStore()
    return AppServices(
        auth_controller=AuthController(auth_repository),
        user_controller=UserController(user_repository, auth_session.require_admin),
        dictamen_controller=DictamenController(
            dictamen_repository,
            inscrito_repository,
            pdf_generator,
            require_admin=auth_session.require_admin,
            reprobado_repository=reprobado_repository,
            create_repository=dictamen_repository,
            search_repository=dictamen_repository,
            update_repository=dictamen_repository,
            delete_repository=dictamen_repository,
        ),
        alumno_controller=AlumnoController(inscrito_repository),
        auth_repository=auth_repository,
        dictamen_repository=dictamen_repository,
        auth_session=auth_session,
        document_store=document_store,
    )
