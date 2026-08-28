# Authenticated session, refresh, and role authorization design

## Context

The frontend already authenticates through `POST /api/auth/login` and keeps both API tokens only in memory. Authenticated repositories share one asynchronous `ApiClient`, but the current login flow creates a placeholder identity from the submitted username, assumes `is_admin=False`, and clears the session immediately on every `401`. The application does not consume `/api/auth/me` or `/api/auth/refresh`, and administrative UI actions are not protected by the authenticated role.

The baseline for this phase is commit `3db2d71` with 349 passing tests. The implementation must preserve the existing Flet architecture, asynchronous HTTPX adapters, request gates, non-optimistic mutations, safe user-facing errors, and in-memory-only credentials.

## Goals

- Establish an authenticated session only after login tokens and `/api/auth/me` both succeed.
- Make `/api/auth/me` the sole source of `id`, `username`, `is_active`, and `is_admin`.
- Keep access token, refresh token, and authenticated user in one shared session object.
- Refresh an expired access token once, rotate both tokens, and retry the original request once.
- Coalesce concurrent refresh attempts when several requests fail with the same access token.
- Clear the complete session when refresh is invalid or the retried request is still unauthorized.
- Give non-administrators the existing queries while preventing every administrative action exposed by the frontend.
- Preserve backend authorization as the final authority.

## Non-goals

- Decoding JWTs in the frontend.
- Persisting sessions across application restarts.
- Implementing backend endpoints, database changes, or token revocation.
- Converting demo user registration or PDF generation to real API adapters.
- Redesigning existing screens or replacing HTTPX/Flet patterns.
- Retrying timeouts, connection failures, server errors, or non-authentication failures.

## Chosen architecture

The existing token-only store will evolve into `AuthSessionStore`. It owns one shared `Session` instance, and that instance contains:

- `access_token`;
- `refresh_token`;
- `authenticated_user`;
- `is_demo`.

`AuthenticatedUser` is an immutable typed model containing `id`, `username`, `is_active`, and `is_admin`. `Session.current_user` exposes the same authenticated user; it does not copy the role. The session and store representations must not reveal either token.

The same session object is shared by `ApiAuthRepository`, `ApiClient`, `AppServices`, `AppContext`, and the authorization guards. Flet receives the session only after identity validation completes. Token rotation mutates the tokens on that shared session, so later requests use the new access token without duplicating state in the UI.

The store supports four explicit transitions:

1. `begin(access_token, refresh_token)` creates a pending API session for `/auth/me`.
2. `authenticate(user)` completes the pending session after validating an active user.
3. `rotate(access_token, refresh_token)` atomically replaces both tokens and discards the previous pair.
4. `clear()` removes both tokens and the authenticated user together.

The demo adapter creates a complete administrator session without API tokens. It follows the same role contract while remaining clearly marked as demo.

## Runtime configuration

`ApiSettings` gains two required paths:

- `auth_me_path` from `RUTA_AUTENTICACION`;
- `refresh_path` from `RUTA_REFRESH`.

The default examples are:

```env
RUTA_AUTENTICACION=/api/auth/me
RUTA_REFRESH=/api/auth/refresh
```

Both values must be relative paths beginning with `/` and must reject hosts, query strings, fragments, and template markers. The obsolete `RUTA_REFRESH_TOKEN` example is replaced to avoid two names for the same endpoint. Repositories, views, and handlers never hardcode either route. Tests inject `ApiSettings` and never depend on `.env`.

## Login and identity flow

`ApiAuthRepository.login()` performs these steps:

1. Clear any previous session.
2. Send `POST` to the configured login path without a Bearer header and with refresh disabled.
3. Validate non-empty access and refresh tokens.
4. Begin a pending session with both tokens.
5. Send authenticated `GET` to the configured `/auth/me` path.
6. Validate the complete user payload and require the exact types expected by the contract.
7. Reject `is_active=False` with a specific safe `InactiveUserError`.
8. Complete the shared session with the returned user and return that same session to Flet.

The username submitted to login is never used as the authenticated identity. The JWT is never decoded for authorization.

The `/auth/me` request uses the central recovery policy, so its first `401` may perform one refresh and one retry. An invalid login `401` maps to the existing credentials error. A failure after tokens are received, including an invalid `/auth/me` response, inactive user, `403`, network error, timeout, or exhausted refresh, clears the pending session. Flet remains on `/login` and shows the safe mapped message. No private layout is rendered before the complete session is published.

## Central refresh and retry flow

`ApiClient.request_json()` remains the single entry point used by authenticated repositories. Its low-level transport operation is separated from authentication recovery so that refresh can call the transport without recursively invoking refresh behavior.

For a normal successful request, no refresh endpoint is called. When an authenticated request receives its first `401`:

1. Capture the access token used by the failed request.
2. Join the current single-flight refresh task when one already exists for that token, otherwise create it.
3. Send `POST` to the configured refresh path without a Bearer header and with exactly `{"refresh_token": "..."}`.
4. Validate both returned tokens.
5. Atomically rotate both values in the shared session.
6. Retry the original method, path, JSON body, query parameters, and expected status once with the new access token.

Requests waiting behind a successful refresh observe that the failed token is no longer current and reuse the rotated pair instead of sending another refresh. A completed refresh task is discarded so a later, independent expiration can renew again.

Login disables recovery explicitly. The internal refresh request bypasses the recovery entry point entirely. Therefore a `401` from refresh cannot cause recursion. The retried original request is also marked as already recovered; a second `401` clears the complete session and raises `SessionExpiredError` without a second refresh.

## Refresh error policy

| Condition | Session result | Request result |
| --- | --- | --- |
| Original request succeeds | unchanged | return response |
| Refresh succeeds, retry succeeds | both tokens rotated | return retry response |
| Refresh returns `401` or `403` | clear tokens and user | `SessionExpiredError` |
| Session has no usable refresh token | clear tokens and user | `SessionExpiredError` |
| Refresh payload is invalid | clear tokens and user | `UnexpectedResponseError` |
| Retry returns `401` | clear tokens and user | `SessionExpiredError` |
| Refresh times out or cannot connect | preserve the complete established session | existing timeout/connection error |
| Refresh returns `5xx` | preserve the complete established session | existing service-unavailable error |

Preserving a complete established session on transient refresh failures retains the valid identity and both original credentials as one coherent unit. The failed original operation is not retried. A later independent operation may attempt a new refresh. During initial login, `ApiAuthRepository` clears even these transient failures because a pending identity must never become a Flet session.

Logs continue to omit request paths, parameters, payloads, response bodies, and tokens.

## Authorization policy

The shared session store exposes an administrator guard that requires an active authenticated user with `is_admin=True`. `UserController` and `DictamenController` receive this guard as a dependency from `build_services()` and `build_demo_services()`.

The guard protects:

- user registration;
- ruling creation and PDF preparation;
- ruling modification;
- ruling deletion.

Read operations for enrolled students, failed subjects, and rulings require only an active session. Login and refresh are authentication operations and are not subject to the administrator guard.

This controller-level protection ensures that a callback invoked directly cannot reach either an HTTP mutation or the demo user repository. View handlers also check the role before changing local mutation state, opening destructive dialogs, or delegating. A denied operation raises the existing `AuthorizationError`; it does not generate `POST`, `PUT`, `PATCH`, or `DELETE` requests.

Backend `403` responses remain authoritative, preserve the session, and use the existing controlled message.

## Role-aware navigation and views

### Administrator

Administrators keep every existing navigation item and action: student queries, failed-subject queries, ruling search/create/update/delete, and demo user creation.

### Non-administrator

The sidebar and dashboard keep the read operations and omit administrative entries. `/usuarios/nuevo` and `/dictamenes/eliminar` are administrator-only routes and redirect a normal user to the dashboard with no protected component rendered.

`/dictamenes/nuevo` remains available as the confirmed read-only query surface. For a normal user it:

- uses a read-only title and description;
- keeps the enrolled/failed source selector, boleta, period, search gate, and result cards;
- omits director, session date, ruling text, PDF preparation, and create action;
- protects the hidden create handler with the administrator guard.

The enrolled-student result hides “Crear dictamen” for a normal user.

The ruling-search view keeps filters, server pagination, loading gates, and results. For a normal user it removes row selection and the modify/delete action row, never opens editors or deletion dialogs, and guards the corresponding callbacks. Administrators retain the current behavior unchanged.

Every role decision reads `session.current_user.is_admin`; no username rule, decoded claim, hardcoded administrator, or separate UI boolean is introduced.

## Expected implementation areas

- `.env.example` and `core/settings.py` for the two validated routes.
- `features/auth/models.py`, the session store, and `core/context.py` for centralized session state.
- `infrastructure/http/auth_repository.py` for login plus `/auth/me`.
- `infrastructure/http/api_client.py` for refresh, rotation, single-flight coordination, and one retry.
- `core/services.py` for one shared session and injected administrator guards.
- `app.py`, `core/routes.py`, `app_shell.py`, dashboard, student, ruling, and user views for role-aware navigation and protected handlers.
- `UserController` and `DictamenController` for mutation guards.

No new dependency is required.

## Test strategy

Implementation follows red-green-refactor. Each production behavior begins with a focused failing test whose failure demonstrates the missing behavior.

### Settings and session

- load and validate both new route variables;
- reject missing or malformed authentication paths;
- establish admin and normal sessions from typed users;
- rotate both tokens and discard the previous pair;
- clear tokens and user together;
- keep representations free of secrets.

### Login and `/auth/me`

- admin and normal login sequences call login before `/auth/me`;
- `/auth/me` receives the correct Bearer access token;
- returned identity, not submitted username, becomes current user;
- inactive and malformed users are rejected;
- `/auth/me` `401`, `403`, timeout, connection failure, and `5xx` leave no pending session;
- invalid credentials retain their existing error semantics.

### Refresh

- valid access returns normally without refresh;
- one `401` triggers exactly one refresh and one retry;
- both tokens rotate and retry uses the new access token;
- invalid refresh clears the complete session with no loop;
- retry `401` performs no second refresh;
- refresh endpoint `401` cannot recurse;
- concurrent failures share one successful refresh;
- transient refresh failures use existing errors and do not retry the original request;
- safe logging assertions continue to exclude sensitive data.

### Authorization and UI

- normal users can call all three query controllers;
- direct normal-user calls to every mutation controller raise before repository invocation;
- administrator mutations continue to work;
- navigation/card/action builders expose the correct controls for each role;
- read-only ruling creation preserves both enrolled and failed-subject searches;
- normal ruling search has no selection, editor, delete confirmation, or mutating callback effect;
- administrative routes reject normal sessions.

### Final verification

- full `uv run pytest` suite;
- Python compilation/import verification;
- `uv lock --check`;
- installed Flet version;
- Flet web startup and HTTP `200`;
- manual smoke for an administrator and a normal user;
- independent code review before final integration.

Unit tests use HTTPX mock transports and never depend on the backend or `.env`.

## Commit strategy

The work is recorded on `feat/auth-session-refresh` without push. Expected atomic units are:

1. design documentation;
2. authenticated identity, session, and settings;
3. centralized refresh and retry;
4. role authorization and read-only UI;
5. final architecture, README, and persistent notes.

Each implementation commit is created only after the relevant focused tests and the full project verification required at that safe point.

## Acceptance criteria

- Admin and normal login both require a successful active `/auth/me` identity.
- A valid access token never triggers refresh.
- An expired access token causes one refresh, complete token rotation, and one retry.
- Invalid refresh or a second `401` clears tokens, user, and Flet session and redirects to login.
- Normal users retain enrolled-student, failed-subject, and ruling queries.
- Normal users cannot cause ruling or user mutations through routes, controls, handlers, or controllers.
- Administrators retain all existing operations.
- No JWT decoding, hardcoded role, refresh loop, stale refresh token, optimistic mutation, new dependency, `.env` change, or push is introduced.
