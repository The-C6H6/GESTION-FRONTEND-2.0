# Project notes

- The application now uses a hybrid composition: login and enrolled-student lookup use HTTP adapters; user registration, failed-subject lookup, rulings, and PDF generation remain on demo adapters.
- Runtime API settings load `API_BASE_URL` (or legacy `IP_ADDRESS`), `RUTA_LOGIN`, and `RUTA_VISUALIZAR_INSCRITOS` through python-dotenv. Unit tests inject settings and never require `.env` or the backend.
- Access and refresh tokens live only in `AuthTokenStore`, are omitted from repr/logs, and are cleared before login, on logout, and on API `401`. A `401` also invalidates the Flet session and redirects to `/login`.
- `ApiInscritoRepository` uses `GET /api/inscritos/{boleta}` and maps the complete API response to `Inscrito`. Both enrolled-student screens show a loading state and reuse the logged-in Bearer token.
- API warning logs intentionally omit request paths because enrolled-student URLs contain the student's boleta.
- API payload data and PDF-only context are separate. Director and eligible subjects belong to `PdfRequest`, not `DictamenCreate`.
- Current-period format is five digits ending in `1` or `2`. Eligible failed subjects satisfy `19 <= current - failed < 29` and cannot be deselected.
- HTTP adapters for registration, failed subjects, rulings, and the real PDF remain intentionally unimplemented. `/api/auth/me` and `/api/auth/refresh` are also deferred. Failed-subject lookup is the recommended next API integration.
- The interface intentionally uses a light content theme with a dark institutional sidebar. Flet eight-digit hex colors use `#AARRGGBB`; theme regression tests protect semantic text contrast and translucent navigation colors.
- `PdfRequest.fecha_sesion` is PDF-only `date` data. Future real PDF adapters must call the shared `build_session_paragraph()`/`format_session_date()` functions instead of formatting dates themselves; the demo exposes the resulting paragraph through `GeneratedDocument.preview_text`.
