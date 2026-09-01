from pathlib import Path

from esiqie_dictamenes.core.settings import ApiSettings
from esiqie_dictamenes.core.services import AppServices
from esiqie_dictamenes.core.session import AuthSessionStore
from esiqie_dictamenes.features.alumnos.controller import AlumnoController
from esiqie_dictamenes.features.auth.controller import AuthController
from esiqie_dictamenes.features.auth.models import (
    AuthenticatedUser,
    RegisteredUser,
    Session,
)
from esiqie_dictamenes.features.dictamenes.controller import DictamenController
from esiqie_dictamenes.features.dictamenes.models import GeneratedDocument
from esiqie_dictamenes.features.usuarios.controller import UserController
from esiqie_dictamenes.infrastructure.demo.alumno_repository import DemoAlumnoRepository
from esiqie_dictamenes.infrastructure.demo.dictamen_repository import (
    DemoDictamenRepository,
)


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


class RecordingUserRepository:
    def __init__(self) -> None:
        self.registered_users: list[RegisteredUser] = []

    async def register(
        self,
        username: str,
        password: str,
        is_admin: bool,
    ) -> RegisteredUser:
        user = RegisteredUser(username=username, is_admin=is_admin)
        self.registered_users.append(user)
        return user


class RecordingPdfGenerator:
    def __init__(
        self,
        document: GeneratedDocument | None = None,
    ) -> None:
        self.calls = []
        self.document = document or GeneratedDocument(
            filename="test.pdf",
            content=b"%PDF-test",
            is_simulation=False,
        )

    async def generate(self, request):
        self.calls.append(request)
        return self.document


class RecordingPdfDocumentStore:
    def __init__(self, saved_path: str | Path = "generated.pdf") -> None:
        self.saved_path = Path(saved_path)
        self.validate_calls = []
        self.save_calls = []

    def validate_destination(self, destination: str | Path) -> Path:
        self.validate_calls.append(destination)
        return Path(destination)

    async def save(self, destination: str | Path, document: bytes) -> Path:
        self.save_calls.append((destination, document))
        return self.saved_path


def build_test_services(
    *,
    is_admin: bool = True,
    pdf_generator: RecordingPdfGenerator | None = None,
    document_store: RecordingPdfDocumentStore | None = None,
) -> AppServices:
    login_repository = RejectingLoginRepository()
    user_repository = RecordingUserRepository()
    alumno_repository = DemoAlumnoRepository()
    dictamen_repository = DemoDictamenRepository()
    pdf_generator = pdf_generator or RecordingPdfGenerator()
    document_store = document_store or RecordingPdfDocumentStore()
    auth_session = authenticated_store(is_admin=is_admin)
    return AppServices(
        auth_controller=AuthController(login_repository),
        user_controller=UserController(user_repository, auth_session.require_admin),
        dictamen_controller=DictamenController(
            dictamen_repository,
            alumno_repository,
            pdf_generator,
            require_admin=auth_session.require_admin,
            search_repository=dictamen_repository,
        ),
        alumno_controller=AlumnoController(alumno_repository),
        auth_repository=login_repository,
        dictamen_repository=dictamen_repository,
        auth_session=auth_session,
        document_store=document_store,
    )


def api_settings(**overrides) -> ApiSettings:
    values = {
        "base_url": "http://api.test",
        "login_path": "/api/auth/login",
        "register_path": "/api/auth/register",
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
