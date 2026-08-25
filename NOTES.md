# Project notes

- The current application uses in-memory demo adapters composed in `core/services.py`; no backend or `.env` access occurs.
- API payload data and PDF-only context are separate. Director and eligible subjects belong to `PdfRequest`, not `DictamenCreate`.
- Current-period format is five digits ending in `1` or `2`. Eligible failed subjects satisfy `19 <= current - failed < 29` and cannot be deselected.
- The real HTTP and PDF adapters remain intentionally unimplemented. Use `.env.example` and `referencias/` when adding them later.
- The interface intentionally uses a light content theme with a dark institutional sidebar. Flet eight-digit hex colors use `#AARRGGBB`; theme regression tests protect semantic text contrast and translucent navigation colors.
