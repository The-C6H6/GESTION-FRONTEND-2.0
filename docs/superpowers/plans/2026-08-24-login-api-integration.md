# Login API Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Connect the existing Flet login form to the FastAPI login endpoint through a reusable asynchronous HTTP layer with in-memory token handling.

**Architecture:** Keep the current UI-to-controller boundary and replace only the login adapter in the production composition. Configuration, HTTP behavior, token state, and API response parsing remain isolated in focused modules; all other repositories and PDF generation stay in demo mode.

**Tech Stack:** Python 3.13, Flet 0.86.5, HTTPX, python-dotenv, pytest, uv

**Spec:** `docs/superpowers/specs/2026-08-24-login-api-integration-design.md`

## Global Constraints

- Do not read or commit `.env`; runtime configuration may load it through python-dotenv.
- Do not integrate `/api/auth/me`, `/api/auth/refresh`, registration, rulings, students, or PDF generation.
- Keep all HTTP I/O asynchronous and outside Flet views.
- Never log credentials, tokens, authentication request bodies, or authorization headers.
- Store access and refresh tokens only in memory and clear them on failed login and logout.
- Use TDD for every production behavior and keep unit tests independent from the real API.
- Use `API_BASE_URL`, falling back to `IP_ADDRESS`, and require `RUTA_LOGIN`.
- Map technical failures to Spanish user-facing messages without HTTP status codes.

---

### Task 1: Declare Direct HTTP Dependencies

**Files:**
- Modify: `pyproject.toml`
- Modify: `uv.lock`

**Interfaces:**
- Consumes: the existing uv-managed virtual environment.
- Produces: direct project dependencies for `httpx` and `python-dotenv`.

- [ ] **Step 1: Add the approved dependencies**

Run:

```powershell
uv add httpx python-dotenv
```

Expected: `pyproject.toml` lists both packages directly and `uv.lock` remains consistent.

- [ ] **Step 2: Verify the existing suite**

Run:

```powershell
uv run pytest
uv lock --check
```

Expected: 56 existing tests pass and the lockfile is current.

- [ ] **Step 3: Commit**

```powershell
git add pyproject.toml uv.lock
git commit -m "chore: add HTTP client dependencies"
```

---

### Task 2: Add Environment Configuration and API Errors

**Files:**
- Create: `src/esiqie_dictamenes/core/settings.py`
- Create: `tests/core/test_settings.py`
- Modify: `src/esiqie_dictamenes/core/errors.py`
- Modify: `tests/core/test_errors.py`

**Interfaces:**
- Consumes: environment variables loaded through `python-dotenv`.
- Produces: `ApiSettings(base_url: str, login_path: str, timeout_seconds: float)` and typed application errors consumed by the HTTP client.

- [ ] **Step 1: Write failing settings tests**

Add tests that define the desired API without touching the process environment:

```python
import pytest

from esiqie_dictamenes.core.errors import ConfigurationError
from esiqie_dictamenes.core.settings import load_api_settings


def test_settings_load_api_base_url_and_login_path():
    settings = load_api_settings(
        {"API_BASE_URL": "http://api.test", "RUTA_LOGIN": "/api/auth/login"}
    )

    assert settings.base_url == "http://api.test"
    assert settings.login_path == "/api/auth/login"
    assert settings.timeout_seconds == 10.0


def test_settings_accept_legacy_ip_address():
    settings = load_api_settings(
        {"IP_ADDRESS": "http://legacy.test", "RUTA_LOGIN": "/login"}
    )

    assert settings.base_url == "http://legacy.test"


@pytest.mark.parametrize("missing", ["base_url", "login_path"])
def test_settings_reject_incomplete_configuration(missing):
    values = {"API_BASE_URL": "http://api.test", "RUTA_LOGIN": "/login"}
    values.pop("API_BASE_URL" if missing == "base_url" else "RUTA_LOGIN")

    with pytest.raises(ConfigurationError):
        load_api_settings(values)
```

- [ ] **Step 2: Run settings tests and verify RED**

Run:

```powershell
uv run pytest tests/core/test_settings.py -v
```

Expected: collection fails because `core.settings` and `ConfigurationError` do not exist.

- [ ] **Step 3: Implement settings and error types**

Implement the public configuration API:

```python
from collections.abc import Mapping
from dataclasses import dataclass
import os

from dotenv import load_dotenv

from esiqie_dictamenes.core.errors import ConfigurationError


@dataclass(frozen=True)
class ApiSettings:
    base_url: str
    login_path: str
    timeout_seconds: float = 10.0


def load_api_settings(environ: Mapping[str, str] | None = None) -> ApiSettings:
    if environ is None:
        load_dotenv()
        environ = os.environ
    base_url = (environ.get("API_BASE_URL") or environ.get("IP_ADDRESS") or "").strip()
    login_path = (environ.get("RUTA_LOGIN") or "").strip()
    if not base_url or not login_path:
        raise ConfigurationError("La configuración de conexión con la API está incompleta.")
    return ApiSettings(base_url=base_url.rstrip("/"), login_path=login_path)
```

Add these subclasses to `core/errors.py`:

```python
class ConfigurationError(AppError):
    """Raised when required runtime configuration is absent or invalid."""


class ApiConnectionError(AppError):
    """Raised when the API cannot be reached."""


class ApiTimeoutError(AppError):
    """Raised when the API exceeds the configured timeout."""


class AuthenticationError(AppError):
    """Raised when supplied credentials are not accepted."""


class AuthorizationError(AppError):
    """Raised when the authenticated identity lacks permission."""


class ServiceUnavailableError(AppError):
    """Raised when the API reports a temporary server failure."""


class UnexpectedResponseError(AppError):
    """Raised when the API response does not match its contract."""
```

- [ ] **Step 4: Add failing error-message tests, then implement exact messages**

Extend `tests/core/test_errors.py` with one assertion for each new error. Verify that `to_user_message()` returns its Spanish message and never includes `401`, `403`, `404`, `422`, or `500`. Use these messages:

```text
No fue posible conectar con el servicio.
El servicio tardó demasiado en responder.
Usuario o contraseña incorrectos.
No tienes permiso para realizar esta acción.
No se encontró el recurso solicitado.
Los datos enviados no son válidos.
El servicio no está disponible temporalmente.
El servicio devolvió una respuesta no válida.
```

Run the focused test before and after the implementation:

```powershell
uv run pytest tests/core/test_errors.py -v
```

- [ ] **Step 5: Verify and commit**

```powershell
uv run pytest tests/core/test_settings.py tests/core/test_errors.py -v
git add src/esiqie_dictamenes/core/settings.py src/esiqie_dictamenes/core/errors.py tests/core/test_settings.py tests/core/test_errors.py
git commit -m "feat: add API runtime configuration"
```

---

### Task 3: Add In-Memory Tokens and the Reusable API Client

**Files:**
- Create: `src/esiqie_dictamenes/infrastructure/http/__init__.py`
- Create: `src/esiqie_dictamenes/infrastructure/http/token_store.py`
- Create: `src/esiqie_dictamenes/infrastructure/http/api_client.py`
- Create: `tests/infrastructure/http/__init__.py`
- Create: `tests/infrastructure/http/test_token_store.py`
- Create: `tests/infrastructure/http/test_api_client.py`

**Interfaces:**
- Consumes: `ApiSettings` and the application error hierarchy from Task 2.
- Produces: `AuthTokenStore.replace(access_token, refresh_token)`, `clear()`, `access_token`, and `ApiClient.request_json(method, path, json=None)`.

- [ ] **Step 1: Write and fail token-store tests**

```python
from esiqie_dictamenes.infrastructure.http.token_store import AuthTokenStore


def test_token_store_replaces_and_clears_tokens():
    store = AuthTokenStore()
    store.replace("access-secret", "refresh-secret")

    assert store.access_token == "access-secret"

    store.clear()
    assert store.access_token is None


def test_token_store_repr_does_not_expose_secrets():
    store = AuthTokenStore()
    store.replace("access-secret", "refresh-secret")

    assert "access-secret" not in repr(store)
    assert "refresh-secret" not in repr(store)
```

Run:

```powershell
uv run pytest tests/infrastructure/http/test_token_store.py -v
```

Expected: FAIL because the module is absent.

- [ ] **Step 2: Implement the minimal token store and verify GREEN**

```python
class AuthTokenStore:
    def __init__(self) -> None:
        self._access_token: str | None = None
        self._refresh_token: str | None = None

    @property
    def access_token(self) -> str | None:
        return self._access_token

    def replace(self, access_token: str, refresh_token: str) -> None:
        self._access_token = access_token
        self._refresh_token = refresh_token

    def clear(self) -> None:
        self._access_token = None
        self._refresh_token = None

    def __repr__(self) -> str:
        return "AuthTokenStore(has_tokens=%s)" % (self._access_token is not None)
```

Run the focused test and confirm both tests pass.

- [ ] **Step 3: Write failing API-client tests**

Use `httpx.MockTransport` and `asyncio.run()` to test real request behavior. The success handler must assert the resolved URL, JSON body, and Bearer header. Add parameterized handlers for 401, 403, 404, 422, and 500, plus handlers that raise `httpx.ConnectError` and `httpx.ReadTimeout`. Add a response with non-JSON content.

The core success shape is:

```python
def test_api_client_sends_json_and_bearer_token():
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "http://api.test/resource"
        assert request.headers["Authorization"] == "Bearer access-secret"
        assert json.loads(request.content) == {"value": 1}
        return httpx.Response(200, json={"ok": True})

    store = AuthTokenStore()
    store.replace("access-secret", "refresh-secret")
    client = ApiClient(
        ApiSettings("http://api.test", "/login"),
        store,
        transport=httpx.MockTransport(handler),
    )

    result = asyncio.run(client.request_json("POST", "/resource", json={"value": 1}))

    assert result == {"ok": True}
```

Run:

```powershell
uv run pytest tests/infrastructure/http/test_api_client.py -v
```

Expected: FAIL because `ApiClient` is absent.

- [ ] **Step 4: Implement the API client**

Implement `request_json()` with this signature:

```python
async def request_json(
    self,
    method: str,
    path: str,
    *,
    json: object | None = None,
) -> object:
```

It must create `httpx.AsyncClient` with `base_url`, `timeout`, and the optional transport inside `async with`, build `Accept: application/json`, add the Bearer header only when a token exists, and call `response.json()` only after status mapping.

Catch `httpx.TimeoutException` before `httpx.RequestError`. Map statuses to the exact Task 2 errors. Map every 5xx status to `ServiceUnavailableError`; map invalid JSON to `UnexpectedResponseError`. Logging may include only method, path, exception type, and status.

- [ ] **Step 5: Verify and commit**

```powershell
uv run pytest tests/infrastructure/http -v
git add src/esiqie_dictamenes/infrastructure/http tests/infrastructure/http
git commit -m "feat: add reusable asynchronous API client"
```

---

### Task 4: Implement the API Login Adapter and Focused Contracts

**Files:**
- Modify: `src/esiqie_dictamenes/features/auth/repository.py`
- Create: `src/esiqie_dictamenes/features/usuarios/repository.py`
- Modify: `src/esiqie_dictamenes/features/usuarios/controller.py`
- Modify: `src/esiqie_dictamenes/infrastructure/demo/auth_repository.py`
- Create: `src/esiqie_dictamenes/infrastructure/http/auth_repository.py`
- Create: `tests/infrastructure/http/test_auth_repository.py`
- Modify: `tests/features/test_auth_and_usuarios.py`

**Interfaces:**
- Consumes: `ApiClient`, `AuthTokenStore`, `Session`, and existing controllers.
- Produces: `LoginRepository.login()`, `UserRepository.register()`, and `ApiAuthRepository.login()`.

- [ ] **Step 1: Write failing login-adapter tests**

Cover a successful response, a missing access token, a non-object JSON value, and token clearing after a failed second login. The success case must assert:

```python
session = asyncio.run(repository.login("directivo", "secreto"))

assert session.username == "directivo"
assert session.is_admin is False
assert session.is_demo is False
assert tokens.access_token == "access-token"
```

The mock handler must also assert the exact login payload and that the login request contains no Authorization header.

Run:

```powershell
uv run pytest tests/infrastructure/http/test_auth_repository.py -v
```

Expected: FAIL because `ApiAuthRepository` is absent.

- [ ] **Step 2: Split repository protocols**

Change `features/auth/repository.py` to expose only:

```python
class LoginRepository(Protocol):
    async def login(self, username: str, password: str) -> Session: ...
```

Create `features/usuarios/repository.py`:

```python
class UserRepository(Protocol):
    async def register(
        self, username: str, password: str, is_admin: bool
    ) -> RegisteredUser: ...
```

Update `AuthController` and `UserController` imports and annotations. Keep `DemoAuthRepository` methods unchanged so it satisfies both protocols structurally.

- [ ] **Step 3: Implement `ApiAuthRepository`**

Use this constructor and signature:

```python
class ApiAuthRepository:
    def __init__(
        self,
        client: ApiClient,
        tokens: AuthTokenStore,
        login_path: str,
    ) -> None: ...

    async def login(self, username: str, password: str) -> Session: ...
```

Clear tokens before the request. Post `{"username": username, "password": password}`. Require a dictionary containing non-empty string values for `access_token` and `refresh_token`; otherwise raise `UnexpectedResponseError`. On any exception, clear the store and re-raise. On success, replace tokens and return `Session(username, is_admin=False, is_demo=False)`.

- [ ] **Step 4: Verify contract and adapter tests**

```powershell
uv run pytest tests/infrastructure/http/test_auth_repository.py tests/features/test_auth_and_usuarios.py -v
```

Expected: all login and registration tests pass.

- [ ] **Step 5: Commit**

```powershell
git add src/esiqie_dictamenes/features/auth src/esiqie_dictamenes/features/usuarios src/esiqie_dictamenes/infrastructure/demo/auth_repository.py src/esiqie_dictamenes/infrastructure/http/auth_repository.py tests/features/test_auth_and_usuarios.py tests/infrastructure/http/test_auth_repository.py
git commit -m "feat: add API login repository"
```

---

### Task 5: Compose Real Login with Demo Modules and Integrate Flet UI

**Files:**
- Modify: `src/esiqie_dictamenes/core/services.py`
- Modify: `src/esiqie_dictamenes/app.py`
- Modify: `src/esiqie_dictamenes/features/auth/view.py`
- Modify: `src/esiqie_dictamenes/shared/components/app_shell.py`
- Modify: `tests/core/test_services.py`
- Modify: `tests/test_app_imports.py`

**Interfaces:**
- Consumes: the API configuration, login adapter, demo adapters, and existing Flet context.
- Produces: `build_services(settings=None, transport=None)` and `AppServices.clear_authentication()`.

- [ ] **Step 1: Write failing service-composition tests**

Add tests that inject `ApiSettings` and `httpx.MockTransport`, then assert:

```python
services = build_services(settings=settings, transport=transport)
session = asyncio.run(services.auth_controller.login("directivo", "secreto"))

assert session.is_demo is False
assert services.auth_tokens.access_token == "access-token"
```

Add a logout-state test:

```python
services.auth_tokens.replace("access-token", "refresh-token")
services.clear_authentication()
assert services.auth_tokens.access_token is None
```

Keep the existing test proving mutable demo repositories are not shared.

- [ ] **Step 2: Run service tests and verify RED**

```powershell
uv run pytest tests/core/test_services.py -v
```

Expected: FAIL because `build_services`, `auth_tokens`, and `clear_authentication` do not exist.

- [ ] **Step 3: Implement hybrid composition**

Extend `AppServices` with `auth_tokens: AuthTokenStore` and a method that clears it. Keep `build_demo_services()` with one demo auth repository. Add:

```python
def build_services(
    settings: ApiSettings | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> AppServices:
    settings = settings or load_api_settings()
    tokens = AuthTokenStore()
    client = ApiClient(settings, tokens, transport=transport)
    login_repository = ApiAuthRepository(client, tokens, settings.login_path)
    user_repository = DemoAuthRepository()
    alumno_repository = DemoAlumnoRepository()
    dictamen_repository = DemoDictamenRepository()
    pdf_generator = DemoPdfGenerator()
    return AppServices(
        auth_controller=AuthController(login_repository),
        user_controller=UserController(user_repository),
        dictamen_controller=DictamenController(
            dictamen_repository, alumno_repository, pdf_generator
        ),
        alumno_controller=AlumnoController(alumno_repository),
        auth_repository=login_repository,
        dictamen_repository=dictamen_repository,
        auth_tokens=tokens,
    )
```

Return `AuthController(login_repository)` and `UserController(user_repository)`. Do not connect any other API endpoint.

- [ ] **Step 4: Integrate Flet without redesigning it**

In `app.py`, replace `build_demo_services` with `build_services` in the `use_state` initializer.

In `LoginView`, replace the demo-credential sentence with:

```text
Ingresa tus credenciales institucionales.
```

Keep the existing async handler, validation, busy state, feedback, and navigation.

In `AppShell.logout()`, call `context.services.clear_authentication()` before clearing the Flet session. Compute the status label from `session.is_demo`:

```python
status = (
    "Modo demostración"
    if context.session and context.session.is_demo
    else "Acceso API · módulos restantes en demostración"
)
```

- [ ] **Step 5: Verify integration**

```powershell
uv run pytest tests/core/test_services.py tests/test_app_imports.py -v
uv run python -m compileall -q src tests
```

Expected: focused tests pass and imports compile without errors.

- [ ] **Step 6: Commit**

```powershell
git add src/esiqie_dictamenes/core/services.py src/esiqie_dictamenes/app.py src/esiqie_dictamenes/features/auth/view.py src/esiqie_dictamenes/shared/components/app_shell.py tests/core/test_services.py tests/test_app_imports.py
git commit -m "feat: connect Flet login to API"
```

---

### Task 6: Document and Verify the Completed Integration

**Files:**
- Modify: `docs/architecture.md`
- Modify: `README.md`
- Modify: `NOTES.md`

**Interfaces:**
- Consumes: the completed runtime behavior from Tasks 1–5.
- Produces: durable execution, architecture, and session-security documentation.

- [ ] **Step 1: Update architecture documentation**

Document the hybrid composition, configuration precedence, in-memory token lifecycle, error mapping boundary, and the fact that `/api/auth/refresh` remains unimplemented.

- [ ] **Step 2: Update README execution guidance**

State that `.env` must provide `API_BASE_URL` or `IP_ADDRESS` plus `RUTA_LOGIN`, that the backend must be available for login, and that other modules still use demo adapters. Do not include credentials or token examples.

- [ ] **Step 3: Update persistent notes**

Replace the note that no backend access occurs with the precise hybrid status. Record that tokens are memory-only and that future HTTP adapters must reuse `ApiClient` and `AuthTokenStore`.

- [ ] **Step 4: Run complete verification**

```powershell
uv run pytest
uv run python -m compileall -q src tests
uv run flet --version
uv lock --check
git diff --check
git status --short
```

Expected: all tests pass, compilation succeeds, Flet reports 0.86.5, the lockfile is current, and only intended documentation changes remain.

- [ ] **Step 5: Commit documentation**

```powershell
git add docs/architecture.md README.md NOTES.md
git commit -m "docs: document API login integration"
```

- [ ] **Step 6: Final clean-tree check**

```powershell
git status --short
git log -6 --oneline
```

Expected: the worktree is clean and the implementation is represented by atomic Conventional Commits.
