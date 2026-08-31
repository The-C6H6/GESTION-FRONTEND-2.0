# Real Dictamen PDF Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace demo PDF output with one real institutional renderer and make CREATE/UPDATE select a safe local destination before their single backend mutation.

**Architecture:** Flet performs local validation and native desktop destination selection, `DictamenController` performs the existing authenticated mutation and delegates to one `PdfGenerator`, and a separate local document store writes the returned bytes with exclusive anti-overwrite naming. The two workflows reconcile the final backend object before any post-mutation PDF failure is reported.

**Tech Stack:** Python 3.13, Flet 0.86.5, HTTPX 0.28.1, fpdf2 2.8.8, PyMuPDF 1.28.2 (dev), pytest 9.1.1, uv.

**Spec:** `docs/superpowers/specs/2026-08-30-real-dictamen-pdf-design.md`

## Global Constraints

- Work only in `C:\dev\FRONTEND 2.0- GESTION-real-pdf-generation` on `feat/real-pdf-generation`; do not push.
- Keep `.env` unread, unchanged, and uncommitted.
- Do not modify the backend, database, or `The-C6H6/GESTION_ESCOLAR_FRONTEND`.
- Reuse only `assets/ipn_logo.jpg`, `assets/logo_esiqie.png`, and `assets/imagen_fondo.png`; do not download or duplicate assets.
- Preserve `AuthSessionStore`, `require_admin()`, `ApiClient`, single-flight refresh, and one authenticated replay.
- Destination confirmation must precede POST/PUT. Cancellation means zero mutation, zero generation, and zero write.
- Use exactly one renderer for CREATE and UPDATE and exactly one collision algorithm.
- `materias=()` is valid and removes the complete table section.
- UPDATE asks again for director/session date and uses `materias=()`.
- Write every behavior test first, observe the expected failure, implement the smallest coherent change, and run focused plus complete verification before every commit.
- Unit tests use recording collaborators, temporary paths, and HTTPX mock transports; they never require the live backend.
- Visual artifacts are temporary under `tmp/pdfs/` and must not be committed.

---

### Task 1: Preserve backend subject metadata through the PDF domain

**Files:**
- Modify: `src/esiqie_dictamenes/features/dictamenes/models.py`
- Modify: `src/esiqie_dictamenes/features/dictamenes/periodos.py`
- Modify: `src/esiqie_dictamenes/infrastructure/http/reprobado_repository.py`
- Modify: `src/esiqie_dictamenes/infrastructure/demo/fixtures.py`
- Modify: `tests/infrastructure/http/test_reprobado_repository.py`
- Modify: `tests/features/dictamenes/test_periodos.py`
- Modify: affected model constructors in `tests/features/dictamenes/`

**Interfaces:**
- Consumes backend fields `Intentos_Ordinario` and `MateriaInscrita` from each `/reprobados` item.
- Produces `MateriaReprobada.intentos_ordinario`, `.materia_inscrita`, and the same fields on `MateriaElegible`.
- Continues validating but does not propagate `InscritoActualmente`.

- [ ] **Step 1: Write failing repository-mapping tests**

Update `REPROBADO_ITEM` assertions to prove that `Intentos_Ordinario=2` and
`MateriaInscrita="SI"` survive parsing. Parametrize `MateriaInscrita` with
`"SI"`, `"NO"`, and `None`. Add invalid cases for a missing/non-integer
`Intentos_Ordinario` and non-string/non-null `MateriaInscrita`.

Assert the resulting model, not only acceptance of the payload:

```python
assert result[0].intentos_ordinario == 2
assert result[0].materia_inscrita == "SI"
assert not hasattr(result[0], "inscrito_actualmente")
```

- [ ] **Step 2: Write failing eligibility-propagation tests**

Construct `MateriaReprobada` with explicit attempts/enrollment values and
assert that every eligible `MateriaElegible` retains them unchanged alongside
the existing computed `diferencia`.

- [ ] **Step 3: Run RED tests**

```powershell
uv run pytest tests/infrastructure/http/test_reprobado_repository.py tests/features/dictamenes/test_periodos.py -q
```

Expected: failures because both domain dataclasses currently discard the two
confirmed backend values.

- [ ] **Step 4: Implement strict propagation**

Add required constructor fields without synthetic defaults:

```python
intentos_ordinario: int
materia_inscrita: str | None
```

Map them in `ApiReprobadoRepository._parse_item()` and carry them through
`eligible_subjects()`. Keep `InscritoActualmente` transport validation exactly
where it is, but do not add it to a PDF/domain dataclass. Update demo fixtures
and test constructors with explicit realistic values.

- [ ] **Step 5: Verify and commit**

```powershell
uv run pytest tests/infrastructure/http/test_reprobado_repository.py tests/features/dictamenes/test_periodos.py tests/features/dictamenes/test_controller.py tests/features/dictamenes/test_create_view.py -q
uv run pytest
uv run python -m compileall -q src tests
uv lock --check
git diff --check
git status --short
git add src/esiqie_dictamenes/features/dictamenes/models.py src/esiqie_dictamenes/features/dictamenes/periodos.py src/esiqie_dictamenes/infrastructure/http/reprobado_repository.py src/esiqie_dictamenes/infrastructure/demo/fixtures.py tests
git commit -m "feat: preserve PDF subject metadata"
```

Expected: all checks pass and `.env` is absent from status.

---

### Task 2: Establish filename, asset, destination, and persistence contracts

**Files:**
- Modify: `src/esiqie_dictamenes/core/errors.py`
- Create: `src/esiqie_dictamenes/core/paths.py`
- Modify: `src/esiqie_dictamenes/features/dictamenes/pdf.py`
- Create: `src/esiqie_dictamenes/infrastructure/pdf/__init__.py`
- Create: `src/esiqie_dictamenes/infrastructure/pdf/document_store.py`
- Create: `tests/core/test_paths.py`
- Create: `tests/infrastructure/pdf/__init__.py`
- Create: `tests/infrastructure/pdf/test_document_store.py`
- Modify: `tests/features/dictamenes/test_pdf_contract.py`

**Interfaces:**
- Produces `build_pdf_filename(dictamen) -> str` using `dictamen.fecha`.
- Produces a `PdfDocumentStore` contract with pre-mutation destination validation and async exclusive persistence.
- Produces safe `PdfGenerationError`, `PdfDestinationError`, and `PdfSaveError` messages.
- Produces `project_assets_dir() -> Path` independent of current working directory.

- [ ] **Step 1: Write failing filename and asset-resolution tests**

Assert:

```python
assert build_pdf_filename(dictamen) == (
    "2021320863_dictamen_2026-08-30.pdf"
)
```

Change the process CWD to `tmp_path` and assert `project_assets_dir()` still
resolves the three existing institutional assets. Do not read `.env`.

- [ ] **Step 2: Write failing destination-validation tests**

Cover an absolute selected `base.pdf`, a missing suffix normalized to `.pdf`,
a custom valid filename, a wrong suffix, a missing parent, and a directory
selected as if it were a file. Validation must occur without creating a file.

- [ ] **Step 3: Write failing anti-overwrite tests**

Using `tmp_path`, verify:

```text
base.pdf absent                -> base.pdf
base.pdf exists                -> base_2.pdf
base.pdf and base_2.pdf exist  -> base_3.pdf
```

Assert the bytes in all pre-existing files remain unchanged. Add an injected
write failure and assert the safe `PdfSaveError` contains no document bytes or
student data.

- [ ] **Step 4: Run RED tests**

```powershell
uv run pytest tests/core/test_paths.py tests/infrastructure/pdf/test_document_store.py tests/features/dictamenes/test_pdf_contract.py -q
```

Expected: collection failures because the contracts and adapters do not exist.

- [ ] **Step 5: Implement the pure filename and path contracts**

Centralize filename generation in `features/dictamenes/pdf.py`. Add an
injectable path resolver based on `Path(__file__).resolve()`, never CWD or a
machine-specific absolute path.

Define destination validation separately from persistence so workflows can
reject invalid picker results before mutating the backend.

- [ ] **Step 6: Implement exclusive collision-safe persistence**

Use a single reusable loop with exclusive creation (`xb`) and `_2`, `_3`, ...
suffixes. Run blocking filesystem work through `asyncio.to_thread`. If writing
fails after exclusive creation, remove only the exact partial file created by
that operation and raise `PdfSaveError`. Never overwrite an existing target.

- [ ] **Step 7: Verify and commit**

```powershell
uv run pytest tests/core/test_paths.py tests/infrastructure/pdf/test_document_store.py tests/features/dictamenes/test_pdf_contract.py -q
uv run pytest
uv run python -m compileall -q src tests
uv lock --check
git diff --check
git status --short
git add src/esiqie_dictamenes/core/errors.py src/esiqie_dictamenes/core/paths.py src/esiqie_dictamenes/features/dictamenes/pdf.py src/esiqie_dictamenes/infrastructure/pdf tests/core/test_paths.py tests/infrastructure/pdf tests/features/dictamenes/test_pdf_contract.py
git commit -m "feat: add collision-safe PDF persistence"
```

---

### Task 3: Render a real institutional PDF without a subjects table

**Files:**
- Create: `src/esiqie_dictamenes/infrastructure/pdf/generator.py`
- Create: `tests/infrastructure/pdf/test_generator.py`
- Modify: `tests/features/dictamenes/test_pdf_contract.py`

**Interfaces:**
- Consumes existing `PdfGenerator.generate(PdfRequest)`.
- Produces real in-memory `GeneratedDocument` bytes with `is_simulation=False`.
- Uses `build_session_paragraph()` and `build_pdf_filename()` rather than duplicating date formatting.

- [ ] **Step 1: Write failing real-PDF tests**

With `materias=()`, assert:

- content begins with a valid PDF signature and is non-empty;
- PyMuPDF opens it as a one-or-more-page document;
- `is_simulation is False`;
- filename is canonical and uses `dictamen.fecha`;
- extracted text contains key, student, boleta, final dictaminacion, exact
  `request.director`, and the shared session paragraph;
- extracted text excludes all four table headers;
- Spanish `Á É Í Ó Ú á é í ó ú Ñ ñ ü` survives extraction;
- there is no artificial empty page.

Add missing-asset and invalid-generation tests that expect a safe
`PdfGenerationError`.

- [ ] **Step 2: Run RED tests**

```powershell
uv run pytest tests/infrastructure/pdf/test_generator.py tests/features/dictamenes/test_pdf_contract.py -q
```

Expected: collection failure because `RealPdfGenerator` does not exist.

- [ ] **Step 3: Implement the first-page institutional renderer**

Use fpdf2 A4 portrait, Helvetica/Helvetica Bold, the three injected assets, and
in-memory output. Implement measured variable blocks for student name,
regulatory paragraph, dictaminacion, and director/signature. Reserve footer
space and emit the institutional footer. Do not implement an empty table path;
skip the table call entirely when `request.materias` is empty.

- [ ] **Step 4: Verify the no-subject renderer and commit**

```powershell
uv run pytest tests/infrastructure/pdf/test_generator.py tests/features/dictamenes/test_pdf_contract.py -q
uv run pytest
uv run python -m compileall -q src tests
uv lock --check
git diff --check
git status --short
git add src/esiqie_dictamenes/infrastructure/pdf/generator.py tests/infrastructure/pdf/test_generator.py tests/features/dictamenes/test_pdf_contract.py
git commit -m "feat: render institutional dictamen PDFs"
```

---

### Task 4: Add the four-column dynamic and multipage subjects table

**Files:**
- Modify: `src/esiqie_dictamenes/infrastructure/pdf/generator.py`
- Modify: `tests/infrastructure/pdf/test_generator.py`

**Interfaces:**
- Consumes `MateriaElegible.materia`, `.periodo_reprobada`, `.intentos_ordinario`, and `.materia_inscrita`.
- Produces measured rows and repeated headers with no row split or footer/signature collision.

- [ ] **Step 1: Write failing one/many-subject tests**

Assert extracted text contains all four headers and the exact values for one
subject, then every value for several subjects including `SI`, `NO`, and a
blank optional value.

- [ ] **Step 2: Write failing long-row geometry test**

Use a subject such as:

```text
PROCESOS DE SEPARACIÓN POR MEMBRANA Y LOS QUE INVOLUCRAN UNA FASE SÓLIDA
```

Use PyMuPDF words/blocks to prove the complete text exists, wraps to more than
one line, remains inside table bounds, and does not overlap the next row.

- [ ] **Step 3: Write failing multipage test**

Generate enough long subjects to require more than one page. Assert:

- every subject appears exactly once;
- every continuation table page contains all four headers;
- no row text is split between pages;
- signature text appears once after the final row;
- row/signature blocks remain above the footer boundary;
- no empty trailing page exists.

- [ ] **Step 4: Run RED tests**

```powershell
uv run pytest tests/infrastructure/pdf/test_generator.py -q
```

Expected: table assertions fail because the renderer currently skips all
subjects.

- [ ] **Step 5: Implement measured table layout**

Measure every cell before drawing. Set row height to the maximum cell height.
Before drawing, compare that height with the actual remaining content area.
Add a continuation page and repeat a compact institutional/table header when
needed. Draw borders using the final row height and keep each row indivisible.
Do not add count-based page-break rules.

- [ ] **Step 6: Verify and commit**

```powershell
uv run pytest tests/infrastructure/pdf/test_generator.py -q
uv run pytest
uv run python -m compileall -q src tests
uv lock --check
git diff --check
git status --short
git add src/esiqie_dictamenes/infrastructure/pdf/generator.py tests/infrastructure/pdf/test_generator.py
git commit -m "feat: render dynamic PDF subject tables"
```

---

### Task 5: Wire real PDF services and one controller generation boundary

**Files:**
- Modify: `src/esiqie_dictamenes/features/dictamenes/controller.py`
- Modify: `src/esiqie_dictamenes/core/services.py`
- Modify: `tests/helpers.py`
- Modify: `tests/features/dictamenes/test_controller.py`
- Modify: `tests/core/test_services.py`
- Modify: `tests/infrastructure/test_demo_repositories.py`
- Remove: `src/esiqie_dictamenes/infrastructure/demo/pdf_generator.py`
- Modify/remove obsolete demo assertions in `tests/features/dictamenes/test_pdf_contract.py`

**Interfaces:**
- Production `build_services()` wires `RealPdfGenerator` and `LocalPdfDocumentStore`.
- `AppServices` exposes the document store but never a Flet picker.
- Controller produces one `generate_pdf(request)` path for both CREATE and UPDATE.
- Controller produces an updated `PdfRequest` from final backend data, captured director/session date, and `materias=()`.

- [ ] **Step 1: Write failing controller-boundary tests**

Use a recording generator to assert `generate_pdf()` calls it exactly once and
returns the exact `GeneratedDocument`. Add `prepare_updated_pdf_request()`
tests proving it:

- rejects blank director or invalid session date before generation;
- uses the final updated `Dictamen` object;
- uses the supplied director/session date;
- always uses `materias=()`;
- calls `require_admin()` before collaborator access.

Replace the obsolete hard-coded `"Dirección ESIQIE"` update simulation test.

- [ ] **Step 2: Write failing service-composition tests**

Assert production services contain `RealPdfGenerator` behind the controller and
a real local store. Assert no production import/reference to `DemoPdfGenerator`
remains. Test services should inject recording/fake adapters and avoid local
file writes unless a test explicitly requests them.

- [ ] **Step 3: Run RED tests**

```powershell
uv run pytest tests/features/dictamenes/test_controller.py tests/core/test_services.py tests/infrastructure/test_demo_repositories.py -q
```

- [ ] **Step 4: Implement composition and remove the dead demo**

Add the controller methods without embedding Flet or filesystem access. Remove
the old `update_and_generate()` signature that hard-codes PDF-only context if
it has no remaining caller. Wire injected assets and the real store in
`build_services()`. Delete `DemoPdfGenerator` only after `rg` proves it is dead.

- [ ] **Step 5: Verify and commit**

```powershell
uv run pytest tests/features/dictamenes/test_controller.py tests/core/test_services.py tests/infrastructure/test_demo_repositories.py tests/features/dictamenes/test_pdf_contract.py -q
uv run pytest
uv run python -m compileall -q src tests
uv lock --check
git diff --check
rg -n "DemoPdfGenerator|infrastructure\.demo\.pdf_generator" src tests
git status --short
git add -A src tests
git commit -m "feat: wire real PDF generation services"
```

Expected: the `rg` command returns no matches.

---

### Task 6: Integrate transactional destination selection into CREATE

**Files:**
- Create: `src/esiqie_dictamenes/features/dictamenes/views/pdf_output.py`
- Modify: `src/esiqie_dictamenes/features/dictamenes/views/crear.py`
- Modify: `tests/features/dictamenes/test_create_view.py`

**Interfaces:**
- Uses memoized Flet 0.86.5 `FilePicker` service and `save_file()` with no bytes on desktop.
- Blocks web/mobile before the picker/backend.
- Produces a testable create workflow with selected path, final backend result, generation, and persistence stages.

- [ ] **Step 1: Write failing Flet-selector tests**

Test a shared pure/platform helper proving web and mobile are unsupported while
Windows/macOS/Linux desktop are supported. Test the picker call uses:

```python
file_name=build_pdf_filename(...)
file_type=ft.FilePickerFileType.CUSTOM
allowed_extensions=["pdf"]
src_bytes omitted
```

Flet 0.86.5 `Service.init()` auto-registers a memoized FilePicker; do not add it
to `page.overlay` or manually append obsolete service controls.

- [ ] **Step 2: Write failing CREATE workflow tests**

With recording selector/controller/store, cover:

- confirmed: one selector, one create, one generation, one write;
- cancelled: one selector, zero create, zero generation, zero write;
- invalid selected path: zero create;
- web/mobile block: zero selector/create;
- backend failure: zero generation/write;
- generation failure after successful POST: one POST, zero retry, created key
  retained, no write, partial-success message;
- write failure after successful POST: one POST, one generation, zero retry,
  created key retained, partial-success message;
- success reports key and actual collision-resolved path;
- request gate releases on cancellation, success, and every failure.

Assert local form validation (including director/dictaminacion/session date) runs
before selection.

- [ ] **Step 3: Run RED tests**

```powershell
uv run pytest tests/features/dictamenes/test_create_view.py -q
```

- [ ] **Step 4: Implement the shared picker helper and staged CREATE flow**

Keep the whole sequence inside the existing create gate. After backend success,
retain the final result before generating. If post-mutation output fails, clear
or invalidate the selected candidate so the same form cannot silently issue a
duplicate POST, while preserving a message with the real created key. Do not
pass document bytes back to FilePicker; persistence stays in the local store.

- [ ] **Step 5: Verify and commit**

```powershell
uv run pytest tests/features/dictamenes/test_create_view.py tests/features/dictamenes/test_controller.py tests/infrastructure/pdf -q
uv run pytest
uv run python -m compileall -q src tests
uv lock --check
git diff --check
git status --short
git add src/esiqie_dictamenes/features/dictamenes/views/pdf_output.py src/esiqie_dictamenes/features/dictamenes/views/crear.py tests/features/dictamenes/test_create_view.py
git commit -m "feat: save created dictamen PDFs transactionally"
```

---

### Task 7: Integrate transactional PDF output into UPDATE

**Files:**
- Modify: `src/esiqie_dictamenes/features/dictamenes/views/modificar.py`
- Modify: `src/esiqie_dictamenes/features/dictamenes/views/buscar.py`
- Modify: `src/esiqie_dictamenes/features/dictamenes/views/pdf_output.py`
- Modify: `tests/features/dictamenes/test_update_view.py`
- Modify: `tests/features/dictamenes/test_search_view.py`

**Interfaces:**
- Update editor captures director and session date.
- Destination selection precedes the one PUT.
- Final backend row is committed before the PDF stage and remains committed after output failure.
- The update PDF uses the shared renderer and `materias=()`.

- [ ] **Step 1: Write failing update-form tests**

Extend `_build_edit_form()` tests to require director, session-date control, and
the existing dictaminacion editor for administrators. Preserve current
read-only role behavior and all search pagination controls.

- [ ] **Step 2: Write failing UPDATE workflow tests**

Cover:

- confirmed: one selector, one PUT, one generation, one write;
- cancel: one selector, zero PUT/generation/write and unchanged remote/local row;
- blank/unchanged dictaminacion: zero selector and zero PUT;
- invalid director/date/path: zero PUT;
- PDF request uses the exact object returned by PUT, not the pre-update row;
- PDF request uses captured director/date and `materias=()`;
- generation/write failure after PUT: one PUT, no replay, updated row retained,
  editor/selection reconciled, controlled partial-success message;
- backend failure: previous row remains and no generation/write occurs;
- web/mobile block: zero selector and zero PUT;
- request gate prevents simultaneous search/update/delete/picker/write and
  releases in all terminal paths.

- [ ] **Step 3: Run RED tests**

```powershell
uv run pytest tests/features/dictamenes/test_update_view.py tests/features/dictamenes/test_search_view.py -q
```

- [ ] **Step 4: Implement update inputs and staged workflow**

Reuse the shared picker helper and store. Validate before selection, then call
the existing update controller once. Commit the final backend row before PDF
generation. Build the update `PdfRequest` through the controller, generate via
the same `generate_pdf()` method as CREATE, and persist via the same store.

- [ ] **Step 5: Verify and commit**

```powershell
uv run pytest tests/features/dictamenes/test_update_view.py tests/features/dictamenes/test_search_view.py tests/features/dictamenes/test_controller.py tests/infrastructure/pdf -q
uv run pytest
uv run python -m compileall -q src tests
uv lock --check
git diff --check
git status --short
git add src/esiqie_dictamenes/features/dictamenes/views/modificar.py src/esiqie_dictamenes/features/dictamenes/views/buscar.py src/esiqie_dictamenes/features/dictamenes/views/pdf_output.py tests/features/dictamenes/test_update_view.py tests/features/dictamenes/test_search_view.py
git commit -m "feat: save updated dictamen PDFs transactionally"
```

---

### Task 8: Validate visuals, document verified behavior, review, and smoke

**Files:**
- Modify: `README.md`
- Modify: `docs/architecture.md`
- Modify: `NOTES.md`
- Modify code/tests only if a review or visual regression first receives a failing test.

**Interfaces:**
- Produces four reviewed PDF fixtures temporarily, final automated evidence,
  user-confirmed desktop/web smoke, and a clean branch ready for integration approval.

- [ ] **Step 1: Run complete automated verification**

```powershell
uv run pytest
uv run python -m compileall -q src tests
uv lock --check
uv run flet --version
git diff --check
rg -n "DemoPdfGenerator|datetime\.now\(|page\.overlay.*FilePicker|src_bytes=.*pdf" src tests
git status --short
```

Expected: all checks pass; forbidden scans have no implementation match; `.env`
is absent from status.

- [ ] **Step 2: Generate deterministic visual cases**

Create only temporary output under `tmp/pdfs/` for:

1. normal dictamen with several `SI`/`NO` subjects;
2. valid dictamen with `materias=()`;
3. extremely long subject/student/director/dictaminacion text;
4. multipage subjects table.

Render every page with PyMuPDF to PNG and inspect them against all three PDFs
in `referencias/`. Record observations for logos, heading, margins, hierarchy,
dictaminacion, four columns, wrapping, borders, continuation headers,
signature, footer, and absence of overlap/empty pages. Remove `tmp/` after the
review.

- [ ] **Step 3: Resolve visual findings test-first**

For every real defect, add a failing geometry/text regression test, implement
the smallest layout correction, rerun focused renderer tests, and repeat the
four-case render. Commit corrections atomically with `fix:` messages.

- [ ] **Step 4: Perform independent whole-branch review**

Review `main...HEAD`, prioritizing:

- mutation occurring before destination confirmation;
- cancellation that still mutates;
- mutation retries outside `ApiClient` authentication recovery;
- stale/optimistic data used for the PDF;
- lost `Intentos_Ordinario`/`MateriaInscrita` values;
- empty table placeholders;
- row/footer/signature collisions;
- silent overwrite or check/write races;
- post-mutation errors reported as cancellation;
- missing authorization or gate release;
- CWD, absolute path, `.env`, backend, historical repo, or dependency drift.

For each valid finding, add a failing test first, fix minimally, run focused and
full verification, and create an atomic `fix:` commit. The independent reviewer
must not modify files directly.

- [ ] **Step 5: Update durable documentation**

Document real PDF generation, the four backend subject fields shown, empty
subjects behavior, domain/session dates, desktop transaction requirement,
web mutation block, anti-overwrite, and partial-success semantics. Update
`NOTES.md` only with final test count, verified visual/startup/smoke facts, and
durable backend caveats.

- [ ] **Step 6: Verify startup**

Start web on port 8501 (or one explicit alternate) and verify HTTP 200 plus the
controlled pre-mutation PDF message. Stop it cleanly. Start the desktop app for
FilePicker smoke; never expose credentials or `.env` contents.

- [ ] **Step 7: Execute user-confirmed smoke**

Administrator smoke:

1. CREATE cancel -> zero backend mutation;
2. CREATE with enrolled/no-subject case -> real PDF without table;
3. CREATE with failed subjects -> four-column real PDF;
4. repeat selected filename -> `_2` while original remains unchanged;
5. UPDATE cancel -> zero PUT;
6. UPDATE with director/session date -> final updated PDF with no table;
7. controlled output failure, if safely reproducible, reports backend success
   separately and does not retry.

Normal-user smoke confirms read workflows remain available and mutation routes
or callbacks remain denied. Only perform real mutations explicitly approved by
the user.

- [ ] **Step 8: Final verification and documentation commit**

```powershell
uv run pytest
uv run python -m compileall -q src tests
uv lock --check
git diff --check
git status --short
git add README.md docs/architecture.md NOTES.md
git commit -m "docs: document real dictamen PDF generation"
```

- [ ] **Step 9: Confirm readiness without integration**

```powershell
git status --short
git log --oneline --decorate main..HEAD
git diff --stat main...HEAD
git diff --name-status main...HEAD
```

Expected: clean worktree, reviewed atomic commits only, no `.env`, no temporary
PDFs, and no backend/historical modifications. Do not merge, push, tag, delete
the branch, or remove the worktree until explicitly authorized.

## Final Report Contract

The completion report must contain exactly the 40 numbered items required by
the phase prompt: baseline, previous state, inspections, reference/backend/
historical analysis, retained/improved/discarded decisions, final architecture,
renderer/table/wrapping/pagination/Unicode/assets details, CREATE/UPDATE/picker/
cancellation/filename/date/collision/failure behavior, file and test changes,
all verification results, visuals, smoke, independent findings/fixes, commits,
and remaining PDF debt.

It must also state explicitly:

```text
The-C6H6/GESTION_ESCOLAR_FRONTEND NO fue modificado.
```

No push.
