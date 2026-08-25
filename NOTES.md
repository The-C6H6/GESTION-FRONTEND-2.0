# Project notes

- The application now uses a hybrid composition: login uses `ApiAuthRepository`, while user registration, students, rulings, and PDF generation remain on demo adapters.
- Runtime API settings load `API_BASE_URL` (or legacy `IP_ADDRESS`) and `RUTA_LOGIN` through python-dotenv. Unit tests inject settings and never require `.env` or the backend.
- Access and refresh tokens live only in `AuthTokenStore`, are omitted from repr/logs, and are cleared before a login attempt and on logout. Future HTTP adapters must reuse `ApiClient` for Bearer headers and error mapping.
- API payload data and PDF-only context are separate. Director and eligible subjects belong to `PdfRequest`, not `DictamenCreate`.
- Current-period format is five digits ending in `1` or `2`. Eligible failed subjects satisfy `19 <= current - failed < 29` and cannot be deselected.
- HTTP adapters other than login and the real PDF adapter remain intentionally unimplemented. `/api/auth/me` and `/api/auth/refresh` are also deferred.
- The interface intentionally uses a light content theme with a dark institutional sidebar. Flet eight-digit hex colors use `#AARRGGBB`; theme regression tests protect semantic text contrast and translucent navigation colors.
- `PdfRequest.fecha_sesion` is PDF-only `date` data. Future real PDF adapters must call the shared `build_session_paragraph()`/`format_session_date()` functions instead of formatting dates themselves; the demo exposes the resulting paragraph through `GeneratedDocument.preview_text`.
