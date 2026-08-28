# Authenticated Session, Refresh, and Role Authorization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish real `/api/auth/me` identity, single-flight `/api/auth/refresh` recovery, and defense-in-depth administrator authorization while preserving every read workflow for normal users.

**Architecture:** Replace the token-only/demo-session split with one in-memory `AuthSessionStore` that owns tokens and the typed authenticated user. `ApiAuthRepository` establishes that store from login plus `/auth/me`; the shared `ApiClient` performs one coordinated refresh and one retry; controllers enforce mutation permissions and Flet views/routes expose only controls allowed by `session.current_user.is_admin`.

**Tech Stack:** Python 3.13, Flet 0.86.5, HTTPX 0.28.1, pytest 9.1.1, python-dotenv, uv.

**Spec:** `docs/superpowers/specs/2026-08-28-auth-session-refresh-authorization-design.md`

## Global Constraints

- Work only in `C:\dev\FRONTEND 2.0- GESTION-auth-session` on `feat/auth-session-refresh`; do not push.
- Keep `.env` unread, unchanged, and uncommitted. Use `.env.example` and injected `ApiSettings` in tests.
- Add no dependency and make no backend or database change.
- `/api/auth/me` is the only identity and role source; never decode JWTs or derive a role from a username.
- `Session` contains only `access_token`, `refresh_token`, and `authenticated_user`; neither `Session`, `AuthSessionStore`, nor another authentication model may expose `is_demo`.
- Remove demo login, demo sessions, authentication fallback, `DemoAuthRepository`, and production `build_demo_services()`; retain only unrelated demo academic, ruling, registration, and PDF adapters.
- Keep tokens only in memory and exclude tokens, credentials, request paths, parameters, payloads, and response bodies from representations and logs.
- Retry only an authenticated request whose first response is `401`; perform at most one refresh and one replay of the exact original request.
- Keep existing request gates and non-optimistic create/update/delete semantics.
- Write each behavior test first, observe the expected failure, implement the smallest coherent change, and run focused plus full verification before every commit.
- Unit tests use `httpx.MockTransport` and never require the live API. Live API access is reserved for final smoke verification.

---

## File Structure

### New files

- `src/esiqie_dictamenes/infrastructure/http/auth_payloads.py`: strict parsers shared by login identity and refresh-token responses.
- `src/esiqie_dictamenes/infrastructure/demo/user_repository.py`: registration-only demo adapter implementing `UserRepository` without authentication behavior.
- `tests/helpers.py`: test-owned settings, authenticated-session, and non-network service factories.
- `tests/core/test_session.py`: session/store transition, authorization, and secret-representation tests.
- `tests/shared/__init__.py` and `tests/shared/components/__init__.py`: test packages for shared controls.
- `tests/shared/components/test_app_shell.py`: role-aware sidebar/header tests.
- `tests/features/dashboard/__init__.py` and `tests/features/dashboard/test_view.py`: role-aware dashboard-card tests.
- `tests/features/alumnos/test_inscritos_view.py`: enrolled-result role presentation tests.

### Replaced or removed files

- Remove `src/esiqie_dictamenes/infrastructure/http/token_store.py`; its responsibility moves to `core/session.py` as `AuthSessionStore`.
- Remove `src/esiqie_dictamenes/infrastructure/demo/auth_repository.py`; registration moves to `DemoUserRepository` and demo login is not replaced.
- Remove `tests/infrastructure/http/test_token_store.py`; its coverage moves to `tests/core/test_session.py`.

### Principal modified files

- `.env.example`, `core/settings.py`: configure and validate `/auth/me` and `/auth/refresh` paths.
- `features/auth/models.py`, `core/session.py`, `core/context.py`: typed identity and single shared in-memory session.
- `infrastructure/http/auth_repository.py`, `infrastructure/http/api_client.py`: login/identity and centralized recovery.
- `core/services.py`: one real store and injected administrator guards; no production demo-auth composition.
- `features/usuarios/controller.py`, `features/dictamenes/controller.py`: mutation authorization boundaries.
- `app.py`, `core/routes.py`, `shared/components/app_shell.py`, `features/dashboard/view.py`: role-aware routing and navigation.
- `features/alumnos/views/inscritos.py`, `features/dictamenes/views/crear.py`, `features/dictamenes/views/buscar.py`, `features/usuarios/view.py`: normal-user read mode plus guarded handlers.
- Existing settings, service, repository, controller, and view tests: migrate constructors to test-owned factories and cover the new behavior.
- `README.md`, `docs/architecture.md`, `NOTES.md`: record the final authenticated architecture and verified behavior.

---

### Task 1: Configure identity and refresh endpoints

**Files:**
- Modify: `.env.example`
- Modify: `src/esiqie_dictamenes/core/settings.py`
- Create: `tests/helpers.py`
- Modify: `tests/core/test_settings.py`
- Modify: `tests/core/test_services.py`
- Modify: `tests/infrastructure/http/test_api_client.py`
- Modify: `tests/infrastructure/http/test_auth_repository.py`
- Modify: `tests/infrastructure/http/test_inscrito_repository.py`
- Modify: `tests/infrastructure/http/test_reprobado_repository.py`
- Modify: `tests/infrastructure/http/test_dictamen_repository.py`

**Interfaces:**
- Consumes: the existing `ApiSettings` constructor and `load_api_settings(environ)` behavior.
- Produces: `ApiSettings.auth_me_path: str`, `ApiSettings.refresh_path: str`, and `tests.helpers.api_settings(**overrides) -> ApiSettings` for every later task.

- [ ] **Step 1: Add failing settings tests and a canonical injected-settings helper**

Create `tests/helpers.py` with the exact constructor used by unit tests:

```python
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
```

Extend `test_settings_load_api_base_url_and_login_path()` to pass and assert:

```python
"RUTA_AUTENTICACION": "/api/auth/me",
"RUTA_REFRESH": "/api/auth/refresh",

assert settings.auth_me_path == "/api/auth/me"
assert settings.refresh_path == "/api/auth/refresh"
```

Add `auth_me_path` and `refresh_path` to the incomplete-configuration parametrization. Add this strict validation case for both environment keys:

```python
@pytest.mark.parametrize(
    ("key", "invalid_path"),
    [
        ("RUTA_AUTENTICACION", "api/auth/me"),
        ("RUTA_AUTENTICACION", "https://api.test/api/auth/me"),
        ("RUTA_AUTENTICACION", "/api/auth/me?detail=true"),
        ("RUTA_AUTENTICACION", "/api/auth/{user}"),
        ("RUTA_REFRESH", "api/auth/refresh"),
        ("RUTA_REFRESH", "https://api.test/api/auth/refresh"),
        ("RUTA_REFRESH", "/api/auth/refresh#token"),
        ("RUTA_REFRESH", "/api/auth/{refresh}"),
    ],
)
def test_settings_reject_invalid_authentication_paths(key, invalid_path):
    values = valid_environment()
    values[key] = invalid_path

    with pytest.raises(ConfigurationError, match="autenticaci|renovaci"):
        load_api_settings(values)
```

Extract `valid_environment()` inside `tests/core/test_settings.py` so every case includes both required variables without copying `.env`.

- [ ] **Step 2: Run the focused settings tests and observe the missing fields**

Run:

```powershell
uv run pytest tests/core/test_settings.py -q
```

Expected: failure because `ApiSettings` has no `auth_me_path`/`refresh_path` and `load_api_settings()` does not require or validate the new variables.

- [ ] **Step 3: Implement required path loading and strict static-path validation**

Add the two fields to `ApiSettings`. In `load_api_settings()`, read exactly `RUTA_AUTENTICACION` and `RUTA_REFRESH`, include them in the completeness check, and validate each through a private helper equivalent to:

```python
def _is_static_api_path(path: str) -> bool:
    parsed = urlsplit(path)
    return (
        path.startswith("/")
        and not parsed.netloc
        and not parsed.query
        and not parsed.fragment
        and "{" not in path
        and "}" not in path
    )
```

Raise safe `ConfigurationError` messages naming the authentication or renewal route, then pass both values into `ApiSettings`. Update `.env.example` to contain:

```env
RUTA_AUTENTICACION=/api/auth/me
RUTA_REFRESH=/api/auth/refresh
```

Remove `RUTA_REFRESH_TOKEN`, `ADMIN_USERNAME`, and `ADMIN_PASSWORD` from `.env.example`. Do not touch `.env`.

- [ ] **Step 4: Migrate injected test settings without changing repository behavior**

Replace direct positional `ApiSettings(...)` calls in the listed service/HTTP tests with `api_settings()` and use keyword overrides such as:

```python
settings = api_settings(dictamen_update_path="/custom/dictaminaciones/{clave}")
```

This migration must not alter HTTP expectations or add live-backend dependencies.

- [ ] **Step 5: Verify the configuration slice and the full suite**

Run:

```powershell
uv run pytest tests/core/test_settings.py tests/infrastructure/http tests/core/test_services.py -q
uv run pytest
uv run python -m compileall -q src tests
uv lock --check
git diff --check
```

Expected: every command succeeds; the full suite count is greater than the 349-test baseline because the new path-validation cases are included.

- [ ] **Step 6: Commit the endpoint configuration**

```powershell
git add .env.example src/esiqie_dictamenes/core/settings.py tests/helpers.py tests/core/test_settings.py tests/core/test_services.py tests/infrastructure/http/test_api_client.py tests/infrastructure/http/test_auth_repository.py tests/infrastructure/http/test_inscrito_repository.py tests/infrastructure/http/test_reprobado_repository.py tests/infrastructure/http/test_dictamen_repository.py
git commit -m "feat: configure authentication session endpoints"
```

---

### Task 2: Establish a typed authenticated session through `/auth/me`

**Files:**
- Modify: `src/esiqie_dictamenes/core/errors.py`
- Modify: `src/esiqie_dictamenes/features/auth/models.py`
- Modify: `src/esiqie_dictamenes/core/session.py`
- Modify: `src/esiqie_dictamenes/core/context.py`
- Create: `src/esiqie_dictamenes/infrastructure/http/auth_payloads.py`
- Modify: `src/esiqie_dictamenes/infrastructure/http/api_client.py`
- Modify: `src/esiqie_dictamenes/infrastructure/http/auth_repository.py`
- Modify: `src/esiqie_dictamenes/core/services.py`
- Create: `src/esiqie_dictamenes/infrastructure/demo/user_repository.py`
- Remove: `src/esiqie_dictamenes/infrastructure/demo/auth_repository.py`
- Remove: `src/esiqie_dictamenes/infrastructure/http/token_store.py`
- Modify: `tests/helpers.py`
- Create: `tests/core/test_session.py`
- Modify: `tests/core/test_routes_and_session.py`
- Modify: `tests/core/test_services.py`
- Modify: `tests/features/test_auth_and_usuarios.py`
- Modify: `tests/infrastructure/test_demo_repositories.py`
- Modify: `tests/infrastructure/http/test_api_client.py`
- Modify: `tests/infrastructure/http/test_auth_repository.py`
- Modify: `tests/infrastructure/http/test_inscrito_repository.py`
- Modify: `tests/infrastructure/http/test_reprobado_repository.py`
- Modify: `tests/infrastructure/http/test_dictamen_repository.py`
- Remove: `tests/infrastructure/http/test_token_store.py`
- Modify: `tests/features/dictamenes/test_create_view.py`
- Modify: `tests/features/dictamenes/test_search_view.py`
- Modify: `tests/features/dictamenes/test_update_view.py`
- Modify: `tests/features/dictamenes/test_delete_view.py`
- Modify: `tests/test_app_imports.py`

**Interfaces:**
- Consumes: `ApiSettings.login_path`, `ApiSettings.auth_me_path`, existing `LoginRepository.login()`, and test `api_settings()`.
- Produces: `AuthenticatedUser`, mutable `Session`, `AuthSessionStore`, `parse_token_pair()`, `parse_authenticated_user()`, `DemoUserRepository`, and real `ApiAuthRepository.login()` returning the exact completed store session.

- [ ] **Step 1: Write failing model and store-transition tests**

Define the intended test helpers in `tests/helpers.py`:

```python
from esiqie_dictamenes.core.session import AuthSessionStore
from esiqie_dictamenes.features.auth.models import AuthenticatedUser


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
```

Create `tests/core/test_session.py` with focused assertions:

```python
def test_store_completes_rotates_and_clears_one_shared_session():
    store = AuthSessionStore()
    pending = store.begin("old-access", "old-refresh")
    user = authenticated_user(is_admin=True)

    completed = store.authenticate(user)
    store.rotate("new-access", "new-refresh")

    assert completed is pending is store.current
    assert completed.current_user is user
    assert (completed.access_token, completed.refresh_token) == (
        "new-access",
        "new-refresh",
    )

    store.clear()
    assert store.current is None
    assert store.current_user is None
```

Also assert that both token strings are absent from `repr(session)` and `repr(store)`, and enforce the exact session data contract plus removal of demo state:

```python
assert tuple(Session.__dataclass_fields__) == (
    "access_token",
    "refresh_token",
    "authenticated_user",
)
assert not hasattr(AuthSessionStore(), "is_demo")
```

Replace the old `SessionState` coverage in `tests/core/test_routes_and_session.py` with completed-store/context invalidation coverage.

- [ ] **Step 2: Run the store tests and observe missing typed-session behavior**

Run:

```powershell
uv run pytest tests/core/test_session.py tests/core/test_routes_and_session.py -q
```

Expected: collection or assertion failure because `AuthenticatedUser` and `AuthSessionStore` do not exist and `Session` still contains username/role/demo fields.

- [ ] **Step 3: Implement the typed models, store, and inactive-user error**

Use these exact model fields:

```python
from dataclasses import dataclass, field


@dataclass(frozen=True)
class AuthenticatedUser:
    id: int
    username: str
    is_active: bool
    is_admin: bool


@dataclass
class Session:
    access_token: str = field(repr=False)
    refresh_token: str = field(repr=False)
    authenticated_user: AuthenticatedUser | None = None

    @property
    def current_user(self) -> AuthenticatedUser | None:
        return self.authenticated_user
```

Replace `SessionState` in `core/session.py` with this store shape and implement the bodies exactly as described:

```python
class AuthSessionStore:
    def __init__(self) -> None:
        self._current: Session | None = None

    @property
    def current(self) -> Session | None:
        return self._current

    @property
    def current_user(self) -> AuthenticatedUser | None:
        if self._current is None:
            return None
        return self._current.current_user

    @property
    def access_token(self) -> str | None:
        if self._current is None:
            return None
        return self._current.access_token

    @property
    def refresh_token(self) -> str | None:
        if self._current is None:
            return None
        return self._current.refresh_token

    @property
    def is_authenticated(self) -> bool:
        user = self.current_user
        return user is not None and user.is_active

    def begin(self, access_token: str, refresh_token: str) -> Session:
        self._current = Session(access_token, refresh_token)
        return self._current

    def authenticate(self, user: AuthenticatedUser) -> Session:
        if self._current is None:
            raise SessionExpiredError()
        self._current.authenticated_user = user
        return self._current

    def rotate(self, access_token: str, refresh_token: str) -> None:
        if self._current is None:
            raise SessionExpiredError()
        self._current.access_token = access_token
        self._current.refresh_token = refresh_token

    def clear(self) -> None:
        self._current = None

    def require_admin(self) -> None:
        user = self.current_user
        if user is None or not user.is_active:
            raise SessionExpiredError()
        if not user.is_admin:
            raise AuthorizationError()

    def __repr__(self) -> str:
        return f"AuthSessionStore(is_authenticated={self.is_authenticated})"
```

Import `AuthorizationError` and `SessionExpiredError` from `core.errors`. `begin()` replaces previous state with a pending `Session`; `authenticate()` attaches the user to that same object; `rotate()` replaces both tokens without replacing the user; `clear()` drops the whole object. The `require_admin()` body becomes the injected controller guard in Task 4.

Add `InactiveUserError(AppError)` with the safe message `"La cuenta de usuario está inactiva."` and let `to_user_message()` map it through the existing `AppError` branch.

- [ ] **Step 4: Write failing login-plus-identity tests**

Rewrite `tests/infrastructure/http/test_auth_repository.py` so its handler returns login tokens and then a user payload. Cover admin and normal roles with exact request ordering:

```python
@pytest.mark.parametrize("is_admin", [True, False])
def test_api_login_publishes_only_the_identity_returned_by_auth_me(is_admin):
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/api/auth/login":
            assert "Authorization" not in request.headers
            return httpx.Response(
                200,
                json={
                    "access_token": "access-token",
                    "refresh_token": "refresh-token",
                },
            )
        assert request.url.path == "/api/auth/me"
        assert request.headers["Authorization"] == "Bearer access-token"
        return httpx.Response(
            200,
            json={
                "id": 7,
                "username": "identity-from-api",
                "is_active": True,
                "is_admin": is_admin,
            },
        )

    repository, store = repository_and_store(handler)
    session = asyncio.run(repository.login("submitted-name", "secreto"))

    assert [request.url.path for request in requests] == [
        "/api/auth/login",
        "/api/auth/me",
    ]
    assert session is store.current
    assert session.current_user.username == "identity-from-api"
    assert session.current_user.is_admin is is_admin
```

Parametrize malformed `/auth/me` payloads: non-dict, missing each required field, boolean `id`, blank username, non-boolean `is_active`, and non-boolean `is_admin`. Assert `UnexpectedResponseError` and `store.current is None`. Assert inactive users raise `InactiveUserError` and clear the pending session. Parametrize `/auth/me` `401`, `403`, timeout, connection error, and `503`; assert the mapped existing error and no pending session. Preserve the invalid-login test and assert `/auth/me` was never called.

- [ ] **Step 5: Run identity tests and observe placeholder-session failures**

Run:

```powershell
uv run pytest tests/infrastructure/http/test_auth_repository.py tests/core/test_services.py -q
```

Expected: failures because login returns the submitted username without calling `/auth/me`, the current client/store are token-only, and pending state is not represented.

- [ ] **Step 6: Implement strict shared payload parsing and real identity establishment**

Create `auth_payloads.py` with:

```python
def parse_token_pair(payload: object) -> tuple[str, str]:
    if not isinstance(payload, dict):
        raise UnexpectedResponseError()
    access_token = payload.get("access_token")
    refresh_token = payload.get("refresh_token")
    if (
        not isinstance(access_token, str)
        or not access_token.strip()
        or not isinstance(refresh_token, str)
        or not refresh_token.strip()
    ):
        raise UnexpectedResponseError()
    return access_token, refresh_token


def parse_authenticated_user(payload: object) -> AuthenticatedUser:
    if not isinstance(payload, dict):
        raise UnexpectedResponseError()
    user_id = payload.get("id")
    username = payload.get("username")
    is_active = payload.get("is_active")
    is_admin = payload.get("is_admin")
    if (
        type(user_id) is not int
        or not isinstance(username, str)
        or not username.strip()
        or type(is_active) is not bool
        or type(is_admin) is not bool
    ):
        raise UnexpectedResponseError()
    return AuthenticatedUser(user_id, username, is_active, is_admin)
```

Change `ApiClient` to read the Bearer token from `AuthSessionStore` and add `authenticated: bool = True` to `request_json()`. When false, omit the header even if a store exists. Keep the current one-shot `401` behavior for this task; Task 3 replaces it with recovery.

Change `ApiAuthRepository` to receive `(client, store, login_path, auth_me_path)`. Clear first, call login with `authenticated=False`, map that request's `SessionExpiredError` to `AuthenticationError`, parse/begin, call authenticated `GET /auth/me`, validate active status, authenticate, and return `store.current`. Any failure after token receipt must clear the pending session.

- [ ] **Step 7: Remove production demo authentication and migrate test-only composition**

Create `DemoUserRepository` containing only `registered_users` and `register()`. Delete `DemoAuthRepository`; update demo repository tests to assert `DemoUserRepository` has no `login` attribute.

Remove `build_demo_services()` from `core/services.py`. Rename the shared field from `auth_tokens` to `auth_session`, create one `AuthSessionStore` in `build_services()`, and pass it to `ApiClient` and `ApiAuthRepository`. Keep `DemoUserRepository`, `DemoAlumnoRepository`, `DemoDictamenRepository`, and `DemoPdfGenerator` only for their explicitly deferred responsibilities.

Extend `tests/helpers.py` with this test-owned composition (Task 4 will add guard arguments to both mutation controllers):

```python
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
        user_controller=UserController(user_repository),
        dictamen_controller=DictamenController(
            dictamen_repository,
            alumno_repository,
            pdf_generator,
        ),
        alumno_controller=AlumnoController(alumno_repository),
        auth_repository=login_repository,
        dictamen_repository=dictamen_repository,
        auth_session=auth_session,
    )
```

Replace every `build_demo_services()` import in the listed tests with this helper. Replace direct `Session(...)` fixtures with `authenticated_store(...).current` and assert the result is not `None` before constructing `AppContextValue`.

Delete `token_store.py` and its test; migrate all HTTP repository tests to `AuthSessionStore` or `authenticated_store()`. Update the shell status test to expect one real-session label and assert no demo-state access.

- [ ] **Step 8: Verify the identity slice and full suite**

Run:

```powershell
uv run pytest tests/core/test_session.py tests/core/test_routes_and_session.py tests/infrastructure/http/test_auth_repository.py tests/core/test_services.py tests/features/test_auth_and_usuarios.py tests/infrastructure/test_demo_repositories.py -q
uv run pytest
uv run python -m compileall -q src tests
uv lock --check
git diff --check
rg -n "DemoAuthRepository|build_demo_services|AuthTokenStore|is_demo" src tests
```

Expected: tests and checks succeed; the final `rg` command returns no matches.

- [ ] **Step 9: Commit the authenticated identity/session slice**

```powershell
git add -A src tests
git commit -m "feat: establish authenticated user sessions"
```

---

### Task 3: Centralize single-flight refresh and one retry

**Files:**
- Modify: `src/esiqie_dictamenes/infrastructure/http/api_client.py`
- Modify: `src/esiqie_dictamenes/infrastructure/http/auth_repository.py`
- Modify: `tests/infrastructure/http/test_api_client.py`
- Modify: `tests/infrastructure/http/test_auth_repository.py`

**Interfaces:**
- Consumes: `AuthSessionStore.access_token`, `.refresh_token`, `.rotate()`, `.clear()`, `parse_token_pair()`, and `ApiSettings.refresh_path`.
- Produces: the full `ApiClient.request_json()` signature documented in Step 5, with at most one refresh/replay and shared concurrent refresh work.

- [ ] **Step 1: Write failing successful-refresh and exact-replay tests**

Add a test whose transport records requests in this exact order:

```python
assert [(request.method, request.url.path) for request in requests] == [
    ("PUT", "/resource"),
    ("POST", "/api/auth/refresh"),
    ("PUT", "/resource"),
]
assert json.loads(requests[1].content) == {"refresh_token": "old-refresh"}
assert "Authorization" not in requests[1].headers
assert requests[2].headers["Authorization"] == "Bearer new-access"
assert json.loads(requests[2].content) == {"value": 1}
assert requests[2].url.params == {"page": "2"}
assert store.current.access_token == "new-access"
assert store.current.refresh_token == "new-refresh"
```

The first resource response is `401`, refresh returns both new tokens, and the replay returns the expected JSON/status. Add a separate test proving a first `200` sends no refresh request.

- [ ] **Step 2: Write failing terminal and transient refresh-policy tests**

Cover these cases independently:

- refresh `401` and `403`: `SessionExpiredError`, complete store cleared, one refresh, no replay;
- absent refresh token/current session: `SessionExpiredError`, store cleared, no refresh HTTP request;
- malformed refresh payload: `UnexpectedResponseError`, complete store cleared;
- replay `401`: `SessionExpiredError`, store cleared, one refresh only;
- refresh timeout/connection failure/`503`: existing error type, original completed session object and old token pair preserved, no replay;
- original `403`: `AuthorizationError`, session preserved, no refresh;
- logs exclude both old/new access/refresh tokens, request path, query, and payload.

For terminal recursion coverage, make `/api/auth/refresh` return `401` and assert the transport sees only the original request plus one refresh request.

- [ ] **Step 3: Write the failing concurrent single-flight test**

Use an async `httpx.MockTransport` handler. Hold both old-token resource requests until both have arrived, return `401` to each, then let refresh return one rotated pair. Execute:

```python
results = await asyncio.gather(
    client.request_json("GET", "/resource", params={"request": 1}),
    client.request_json("GET", "/resource", params={"request": 2}),
)

assert results == [{"request": "1"}, {"request": "2"}]
assert refresh_calls == 1
assert old_token_calls == 2
assert new_token_calls == 2
```

The handler must echo the request query only after seeing `Bearer new-access`, proving both original requests were replayed and neither payload was cross-wired.

- [ ] **Step 4: Run refresh tests and observe immediate-session-expiry failures**

Run:

```powershell
uv run pytest tests/infrastructure/http/test_api_client.py -q
```

Expected: failures because the current `401` branch clears the store and never calls refresh or replays the request.

- [ ] **Step 5: Separate transport, status mapping, JSON decoding, and recovery**

Refactor `ApiClient` so `_send_request()` performs exactly one HTTPX request and maps only timeout/connection failures; it returns `httpx.Response` without authentication recursion. Keep `_raise_for_status()` free of session mutation. Keep JSON decoding and `expected_status` validation after authentication recovery selects the final response.

`request_json()` must accept:

```python
async def request_json(
    self,
    method: str,
    path: str,
    *,
    json: object | None = None,
    params: Mapping[str, str | int] | None = None,
    expected_status: int | None = None,
    authenticated: bool = True,
    allow_refresh: bool = True,
) -> object:
```

Capture the access token used by the first request. On its first `401`, recover only when both flags are true. Replay method/path/body/params/expected status once with the rotated access token. A replay `401` clears and raises `SessionExpiredError`; it never re-enters `request_json()`.

- [ ] **Step 6: Implement one shared refresh task per failed access token**

Maintain an `asyncio.Lock`, the current refresh `Task[None]`, and the access token associated with that task. Under the lock:

1. return immediately when the store already has a different access token;
2. join the existing task when it belongs to the failed token;
3. otherwise create exactly one task that calls `_perform_refresh()`.

`_perform_refresh()` reads the current refresh token, calls `_send_request("POST", settings.refresh_path, json={"refresh_token": token}, access_token=None)`, handles `401/403` as terminal expiry, maps other status codes normally, parses both new tokens, and calls `store.rotate()` atomically. Clear the task reference after all current waiters can observe its result so a later independent expiry may create a new task.

On malformed token payload, absent refresh state, or terminal unauthorized response, clear the store. On timeout, connection failure, or `5xx`, do not mutate a complete established store. Never log token values or request data.

- [ ] **Step 7: Make login bypass recovery and verify pending-session cleanup**

Call login with `authenticated=False, allow_refresh=False`. `/auth/me` keeps the defaults, so its first `401` can refresh once. Add an auth-repository test proving login → `/auth/me` `401` → refresh → `/auth/me` retry succeeds.

Parametrize refresh timeout, connection failure, and `503` during `/auth/me`; although the client preserves its input store, `ApiAuthRepository.login()` must clear the pending session before propagating the error. This distinguishes pending login from an established application session.

- [ ] **Step 8: Verify recovery and full regression**

Run:

```powershell
uv run pytest tests/infrastructure/http/test_api_client.py tests/infrastructure/http/test_auth_repository.py -q
uv run pytest
uv run python -m compileall -q src tests
uv lock --check
git diff --check
```

Expected: all commands succeed, with exactly one refresh in the concurrency and terminal-loop tests.

- [ ] **Step 9: Commit centralized recovery**

```powershell
git add src/esiqie_dictamenes/infrastructure/http/api_client.py src/esiqie_dictamenes/infrastructure/http/auth_repository.py tests/infrastructure/http/test_api_client.py tests/infrastructure/http/test_auth_repository.py
git commit -m "feat: refresh expired API sessions once"
```

---

### Task 4: Enforce administrator authorization in controllers

**Files:**
- Modify: `src/esiqie_dictamenes/features/usuarios/controller.py`
- Modify: `src/esiqie_dictamenes/features/dictamenes/controller.py`
- Modify: `src/esiqie_dictamenes/core/services.py`
- Modify: `tests/helpers.py`
- Modify: `tests/features/test_auth_and_usuarios.py`
- Modify: `tests/features/dictamenes/test_controller.py`
- Modify: `tests/core/test_services.py`

**Interfaces:**
- Consumes: `AuthSessionStore.require_admin() -> None` from Task 2.
- Produces: required `require_admin: Callable[[], None]` dependencies for `UserController` and `DictamenController`; all mutation entry points fail before repository/PDF invocation for normal users.

- [ ] **Step 1: Write failing user-registration authorization tests**

Use a recording `DemoUserRepository` and two explicit stores:

```python
normal_store = authenticated_store(is_admin=False)
repository = DemoUserRepository()
controller = UserController(repository, normal_store.require_admin)

with pytest.raises(AuthorizationError):
    asyncio.run(controller.register("nuevo", "secreto", "secreto", False))

assert repository.registered_users == []
```

Add the corresponding admin test and assert exactly one registered user. Also call the normal-user case with invalid form data and assert authorization occurs before validation or repository access.

- [ ] **Step 2: Write failing ruling-mutation authorization tests**

Build recording create/update/delete repositories plus a PDF generator that raises if called. For a normal store, independently call `create()`, `update()`, `update_dictaminacion()`, `update_and_generate()`, and `delete_dictamenes()`. Each must raise `AuthorizationError` before any repository call. Keep query tests using that same normal guard and prove `find_student_candidate()` and `search_page()` still delegate successfully.

For an administrator, retain existing create/update/delete assertions and add `require_admin=admin_store.require_admin` to every test controller constructor.

- [ ] **Step 3: Run controller tests and observe unauthorized delegation**

Run:

```powershell
uv run pytest tests/features/test_auth_and_usuarios.py tests/features/dictamenes/test_controller.py -q
```

Expected: normal-user mutation tests fail because controllers do not yet depend on the session guard.

- [ ] **Step 4: Inject and call the guard at every public mutation boundary**

Change the constructors to require the guard:

```python
class UserController:
    def __init__(self, repository: UserRepository, require_admin: Callable[[], None]) -> None:
        self._repository = repository
        self._require_admin = require_admin
```

```python
class DictamenController:
    def __init__(
        self,
        repository: DictamenRepository,
        alumno_repository: InscritoRepository,
        pdf_generator: PdfGenerator,
        *,
        require_admin: Callable[[], None],
        reprobado_repository: ReprobadoRepository | None = None,
        create_repository: DictamenCreateRepository | None = None,
        search_repository: DictamenSearchRepository | None = None,
        update_repository: DictamenUpdateRepository | None = None,
        delete_repository: DictamenDeleteRepository | None = None,
    ) -> None:
```

Call `self._require_admin()` as the first statement of `UserController.register()` and of `DictamenController.create()`, `update()`, `update_dictaminacion()`, `update_and_generate()`, and `delete_dictamenes()`. Avoid a double repository/PDF operation; `update_and_generate()` may rely on guarded `update()` but must not expose an unguarded alternate path.

- [ ] **Step 5: Wire one guard through production and test-owned composition**

In `build_services()`, pass `auth_session.require_admin` to both controllers. In `tests.helpers.build_test_services()`, seed the requested role and inject that store's guard. Update all existing `DictamenController` test constructors to pass an explicit admin guard; do not add an allow-all default to production constructors.

Update service transport fixtures so login includes `/auth/me`. Prove a normal production-composed session can query enrolled/failed/rulings, but user registration and ruling POST/PUT/DELETE raise before their transport/demo repositories receive a call. Prove admin composition retains those calls.

- [ ] **Step 6: Verify controller authorization and full regression**

Run:

```powershell
uv run pytest tests/features/test_auth_and_usuarios.py tests/features/dictamenes/test_controller.py tests/core/test_services.py -q
uv run pytest
uv run python -m compileall -q src tests
uv lock --check
git diff --check
```

Expected: all commands succeed; normal query tests pass and every normal mutation records zero calls.

- [ ] **Step 7: Commit controller authorization**

```powershell
git add src/esiqie_dictamenes/features/usuarios/controller.py src/esiqie_dictamenes/features/dictamenes/controller.py src/esiqie_dictamenes/core/services.py tests/helpers.py tests/features/test_auth_and_usuarios.py tests/features/dictamenes/test_controller.py tests/core/test_services.py
git commit -m "feat: enforce administrator mutation guards"
```

---

### Task 5: Make private routes and navigation role-aware

**Files:**
- Modify: `src/esiqie_dictamenes/core/routes.py`
- Modify: `src/esiqie_dictamenes/app.py`
- Modify: `src/esiqie_dictamenes/shared/components/app_shell.py`
- Modify: `src/esiqie_dictamenes/features/dashboard/view.py`
- Modify: `tests/core/test_routes_and_session.py`
- Create: `tests/shared/__init__.py`
- Create: `tests/shared/components/__init__.py`
- Create: `tests/shared/components/test_app_shell.py`
- Create: `tests/features/dashboard/__init__.py`
- Create: `tests/features/dashboard/test_view.py`
- Modify: `tests/test_app_imports.py`

**Interfaces:**
- Consumes: a completed `Session.current_user` from Task 2.
- Produces: `is_admin_route(path)`, `_private_route_redirect(path, session)`, `_navigation_items(user)`, and `_dashboard_cards(user)` used directly by Flet composition and unit tests.

- [ ] **Step 1: Write failing route-authorization tests**

Add exact assertions:

```python
@pytest.mark.parametrize(
    "route",
    [RoutePath.NUEVO_USUARIO, RoutePath.ELIMINAR_DICTAMENES],
)
def test_administrative_routes_redirect_normal_users_without_rendering(route):
    session = authenticated_store(is_admin=False).current
    assert session is not None
    assert is_admin_route(route) is True
    assert _private_route_redirect(route, session) == RoutePath.DASHBOARD


def test_read_only_ruling_candidate_route_remains_available_to_normal_users():
    session = authenticated_store(is_admin=False).current
    assert session is not None
    assert _private_route_redirect(RoutePath.NUEVO_DICTAMEN, session) is None
```

Retain unauthenticated private-route redirection to login and prove admins receive no redirect for every private route.

- [ ] **Step 2: Write failing navigation and dashboard tests**

Test `_navigation_items(authenticated_user(is_admin=False))` includes dashboard, ruling search, candidate/student query, and enrolled lookup; it must exclude delete and user creation. Assert admin items retain every existing route. Test `_dashboard_cards()` with the same role matrix and verify the normal label for `/dictamenes/nuevo` is read-only wording such as `"Consultar alumnos"`, not `"Nuevo dictamen"`.

Update the status-label test to expect one safe truthful label, `"Acceso API · registro y PDF en demostración"`, and the `/auth/me` username from `session.current_user.username`.

- [ ] **Step 3: Run navigation tests and observe unrestricted routes/items**

Run:

```powershell
uv run pytest tests/core/test_routes_and_session.py tests/shared/components/test_app_shell.py tests/features/dashboard/test_view.py tests/test_app_imports.py -q
```

Expected: failures because admin routes are not classified and sidebar/dashboard items are unconditional.

- [ ] **Step 4: Implement route denial before outlet rendering**

Add `is_admin_route()` for exactly `/usuarios/nuevo` and `/dictamenes/eliminar`. Add a pure `_private_route_redirect(path, session)` in `app.py`:

```python
def _private_route_redirect(path: str, session: Session | None) -> RoutePath | None:
    if (
        session is None
        or session.current_user is None
        or not session.current_user.is_active
    ):
        return RoutePath.LOGIN
    if is_admin_route(path) and not session.current_user.is_admin:
        return RoutePath.DASHBOARD
    return None
```

In `_private_layout()`, compute that target from `ft.context.page.route`, schedule navigation with the existing effect pattern, and return the progress container whenever a redirect target exists. Only call `ft.use_route_outlet()` after the target is `None`, so a denied component is never rendered.

- [ ] **Step 5: Build sidebar and dashboard items from the authenticated user**

Extract tuple builders that accept `AuthenticatedUser`, inspect only `.is_admin`, and feed the current rendering loops. Keep normal users on:

- Inicio;
- Buscar dictámenes;
- Consultar alumnos (`/dictamenes/nuevo`);
- Buscar inscrito.

Append Eliminar dictámenes and Crear usuario only for admins, while admins retain `Dictaminar` wording for `/dictamenes/nuevo`. Read the header username only through `context.session.current_user.username`. Remove all demo-session branching.

- [ ] **Step 6: Verify route/navigation behavior and full regression**

Run:

```powershell
uv run pytest tests/core/test_routes_and_session.py tests/shared/components/test_app_shell.py tests/features/dashboard/test_view.py tests/test_app_imports.py -q
uv run pytest
uv run python -m compileall -q src tests
uv lock --check
git diff --check
```

Expected: all commands succeed; no normal navigation builder exposes either admin-only route.

- [ ] **Step 7: Commit role-aware routes and navigation**

```powershell
git add src/esiqie_dictamenes/core/routes.py src/esiqie_dictamenes/app.py src/esiqie_dictamenes/shared/components/app_shell.py src/esiqie_dictamenes/features/dashboard/view.py tests/core/test_routes_and_session.py tests/shared tests/features/dashboard tests/test_app_imports.py
git commit -m "feat: restrict administrative navigation by role"
```

---

### Task 6: Preserve normal-user queries while removing mutation UI

**Files:**
- Modify: `src/esiqie_dictamenes/features/alumnos/views/inscritos.py`
- Modify: `src/esiqie_dictamenes/features/dictamenes/views/crear.py`
- Modify: `src/esiqie_dictamenes/features/dictamenes/views/buscar.py`
- Modify: `src/esiqie_dictamenes/features/dictamenes/views/eliminar.py`
- Modify: `src/esiqie_dictamenes/features/usuarios/view.py`
- Create: `tests/features/alumnos/test_inscritos_view.py`
- Modify: `tests/features/dictamenes/test_create_view.py`
- Modify: `tests/features/dictamenes/test_search_view.py`
- Modify: `tests/features/dictamenes/test_update_view.py`
- Modify: `tests/features/dictamenes/test_delete_view.py`
- Modify: `tests/features/test_auth_and_usuarios.py`

**Interfaces:**
- Consumes: completed `session.current_user`, `AuthSessionStore.require_admin()`, and guarded controllers.
- Produces: read-only student/ruling controls for normal users, selectable/mutating controls for admins, and `_run_admin_action(require_admin, action)` for handler-level defense.

- [ ] **Step 1: Write failing enrolled-result and candidate-screen role tests**

Extract an enrolled-details builder receiving `AuthenticatedUser`. Assert an admin result contains a button keyed `inscrito-create-dictamen`; assert a normal result contains the same academic texts but no button navigating to `/dictamenes/nuevo`.

For `crear.py`, add a pure copy helper and an admin-control filter:

```python
def _page_copy(user: AuthenticatedUser) -> tuple[str, str]:
    if user.is_admin:
        return (
            "Nuevo dictamen",
            "Selecciona el tipo de alumno y captura los datos de la sesión.",
        )
    return (
        "Consultar alumnos",
        "Consulta alumnos inscritos o con materias reprobadas.",
    )


def _admin_controls(
    user: AuthenticatedUser,
    controls: tuple[ft.Control, ...],
) -> tuple[ft.Control, ...]:
    return controls if user.is_admin else ()
```

Test that normal users retain the source dropdown, boleta, period, search button, result/failed-subject section, and request gate, while `_admin_controls()` removes director, session-date, dictaminación, PDF preparation, and create controls. Admin assertions preserve all current keys.

- [ ] **Step 2: Write failing read-only ruling-search tests**

Change `_build_results_table()` and `_build_selection_actions()` tests to pass an `AuthenticatedUser`. For normal users assert:

```python
assert table.show_checkbox_column is False
assert row.selected is False
assert row.on_select_change is None
assert isinstance(actions, ft.Container)
assert actions.content is None
```

For admins, retain checkbox selection, modify, and delete assertions. Filters, pagination, result cells, and loading behavior must be identical for both roles.

Add `_run_admin_action()` coverage for synchronous editor/dialog state changes:

```python
called = []
with pytest.raises(AuthorizationError):
    buscar._run_admin_action(
        authenticated_store(is_admin=False).require_admin,
        lambda: called.append(True),
    )
assert called == []
```

Use the helper in editor/dialog openers before local state changes. For asynchronous mutations, test focused delegators: `crear._create_dictamen(services, ...)`, `buscar._load_update(..., require_admin=...)`, `eliminar._load_delete(..., require_admin=...)`, and `usuarios._register_user(services, ...)`. Each delegator calls `require_admin()` before awaiting its controller.

- [ ] **Step 3: Run the view tests and observe unconditional mutation controls**

Run:

```powershell
uv run pytest tests/features/dictamenes/test_create_view.py tests/features/dictamenes/test_search_view.py tests/features/dictamenes/test_update_view.py tests/features/dictamenes/test_delete_view.py tests/features/test_auth_and_usuarios.py -q
```

Expected: failures because controls are still unconditional and handlers have no view-level guard.

- [ ] **Step 4: Implement the normal-user candidate query mode**

In `DictamenCreateView`, derive `user = context.session.current_user` and require it to be present. Keep source, boleta, period, search handler, request gate, loading indicator, candidate identity, and failed-subject/eligibility result for both roles. Use `_page_copy(user)` for the heading. Build director, session date, dictaminación, PDF-related text, and create button as one tuple passed through `_admin_controls(user, ...)` before adding it to the column.

Make the create handler delegate through `_create_dictamen()`, whose first statement calls `services.auth_session.require_admin()` before `dictamen_controller.create()`. Perform that guarded delegation before committing success state. Map `AuthorizationError` through `to_user_message()` without an HTTP request.

- [ ] **Step 5: Implement read-only enrolled and ruling results**

In `InscritoSearchView`, construct the result card through the extracted builder and include `Crear dictamen` only when `user.is_admin`.

In `DictamenSearchView`, pass the current user to result/action builders. A normal table has no selection behavior, and its action builder returns an empty container. Only admins compose edit form and deletion confirmation. Wrap `open_editor()` and `open_delete_confirmation()` with `_run_admin_action()` as their first effect. Pass `context.services.auth_session.require_admin` into `_load_update()` and `_load_delete()` so save/delete delegation is guarded before controller access. Denial sets the controlled permission message and does not alter selection/editor/dialog/request-gate state.

In `CreateUserView.submit()`, delegate through `_register_user()`, which calls `services.auth_session.require_admin()` before `user_controller.register()`. This is defense in depth even though Task 5 prevents the component from rendering for normal users.

- [ ] **Step 6: Prove hidden/direct callbacks cannot mutate**

Use recording repositories/controllers in the view helper tests. Invoke the guarded helper with a normal store and assert no registration/create/update/delete call, no dialog-opening callback, and no state callback occurred. Invoke it with an admin store and assert the supplied action runs once. Retain controller-level zero-call assertions from Task 4.

- [ ] **Step 7: Verify role-aware views and full regression**

Run:

```powershell
uv run pytest tests/features/alumnos tests/features/dictamenes tests/features/test_auth_and_usuarios.py -q
uv run pytest
uv run python -m compileall -q src tests
uv lock --check
git diff --check
```

Expected: all commands succeed; normal role tests retain all three query families and expose no mutation control or callback effect.

- [ ] **Step 8: Commit role-aware read-only UI**

```powershell
git add src/esiqie_dictamenes/features/alumnos/views/inscritos.py src/esiqie_dictamenes/features/dictamenes/views/crear.py src/esiqie_dictamenes/features/dictamenes/views/buscar.py src/esiqie_dictamenes/features/dictamenes/views/eliminar.py src/esiqie_dictamenes/features/usuarios/view.py tests/features
git commit -m "feat: provide role-aware read-only views"
```

---

### Task 7: Document, review, and smoke-test the completed phase

**Files:**
- Modify: `README.md`
- Modify: `docs/architecture.md`
- Modify: `NOTES.md`

**Interfaces:**
- Consumes: the completed behavior and observed verification results from Tasks 1–6.
- Produces: accurate operator/developer documentation and a final safe integration commit on `feat/auth-session-refresh`.

- [ ] **Step 1: Update durable documentation from verified behavior**

Update `README.md` and `docs/architecture.md` to state:

- login is `POST /api/auth/login` followed by `GET /api/auth/me`;
- identity/role come only from `/auth/me`;
- access/refresh/user live in one ephemeral in-memory session;
- authenticated `401` performs one single-flight refresh and one replay;
- terminal refresh/replay expiry clears the complete session, while transient refresh errors preserve an established session;
- controller guards and role-aware routes/views protect admin mutations;
- normal users retain enrolled, failed-subject, and ruling queries;
- user registration and PDF remain demo-backed, but authentication never is.

Update the runtime-variable section to use `RUTA_AUTENTICACION` and `RUTA_REFRESH` and remove obsolete credential/demo-auth wording.

Update `NOTES.md` only with future-use facts: the completed phase behavior, final test count, verified Flet/startup/smoke results, and any durable backend contract caveat. Remove the old note saying `/api/auth/me` and `/api/auth/refresh` are deferred. Do not record credentials, temporary ports, transient failures, or implementation narration.

- [ ] **Step 2: Run the complete automated verification before documentation commit**

Run:

```powershell
uv run pytest
uv run python -m compileall -q src tests
uv lock --check
uv run flet --version
git diff --check
rg -n "DemoAuthRepository|build_demo_services|AuthTokenStore|is_demo|RUTA_REFRESH_TOKEN|ADMIN_USERNAME|ADMIN_PASSWORD" src tests .env.example README.md docs NOTES.md
git status --short
```

Expected: tests, compilation, lock, and diff checks succeed; Flet reports 0.86.5 or the resolved compatible version; the forbidden-term scan returns no matches except historical design material that explicitly describes removal. Confirm `.env` is absent from `git status --short`.

- [ ] **Step 3: Start Flet web and verify HTTP startup**

Start the worktree application without exposing environment contents:

```powershell
uv run flet run --web --port 8501
```

In a second terminal, run:

```powershell
(Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8501).StatusCode
```

Expected: `200`. Keep the process available for browser smoke; stop it cleanly with Ctrl+C afterward. If port 8501 is occupied, use one explicit alternate port and report it without changing project files.

- [ ] **Step 4: Execute real administrator smoke without recording credentials**

Using credentials entered interactively by the user, never printed or persisted by the agent:

1. Login and verify `/auth/me` identity appears in the header.
2. Verify admin sidebar/dashboard contain Dictaminar, Eliminar dictámenes, and Crear usuario.
3. Query one enrolled student, one failed-student result, and one ruling page.
4. Verify the ruling search exposes selection, modify, and delete controls.
5. Exercise only mutations the user explicitly approves; confirm backend `403` remains a controlled message and does not clear the session.
6. Logout and confirm the private area returns to `/login`.

- [ ] **Step 5: Execute real normal-user smoke without recording credentials**

Using a normal account entered interactively by the user:

1. Login and verify `/auth/me` identity appears in the header.
2. Verify sidebar/dashboard omit Eliminar dictámenes and Crear usuario and label `/dictamenes/nuevo` as a query.
3. Open `/dictamenes/nuevo`; query both enrolled and failed-student sources and confirm director/date/dictaminación/PDF/create controls are absent.
4. Query rulings and confirm rows have no selection, edit, or delete actions.
5. Enter `/usuarios/nuevo` and `/dictamenes/eliminar` directly; confirm both redirect to `/` without rendering protected content.
6. Confirm enrolled results omit Crear dictamen, then logout to `/login`.

- [ ] **Step 6: Perform independent code review and resolve findings**

Review the complete branch diff against the approved spec, prioritizing:

- retry recursion or more than one replay;
- races or stale-token use in concurrent refresh;
- transient versus terminal session clearing;
- tokens/credentials in logs or representations;
- controller paths that can mutate without `require_admin()`;
- normal-user controls/routes that still expose mutations;
- accidental `.env`, dependency, backend, or database changes.

For every valid finding, write a failing regression test first, implement the minimal correction, rerun its focused tests, and repeat the complete verification from Step 2. Do not rewrite existing commits; create an atomic `fix:` commit if a code correction is required.

- [ ] **Step 7: Record final verified facts and commit documentation**

After automated checks, startup, both smoke roles, and review are complete, insert the observed test count and verification facts into `NOTES.md`, then run:

```powershell
uv run pytest
uv run python -m compileall -q src tests
uv lock --check
git diff --check
git status --short
```

Expected: all checks succeed and only `README.md`, `docs/architecture.md`, and `NOTES.md` are staged for this commit.

```powershell
git add README.md docs/architecture.md NOTES.md
git commit -m "docs: document authenticated role sessions"
```

- [ ] **Step 8: Confirm the branch is ready for explicit local integration approval**

Run:

```powershell
git status --short
git log --oneline --decorate main..HEAD
git diff --stat main...HEAD
```

Expected: clean worktree and only the reviewed atomic commits on `feat/auth-session-refresh`. Do not merge, remove the worktree, delete the branch, tag, or push until the user explicitly authorizes the corresponding action.
