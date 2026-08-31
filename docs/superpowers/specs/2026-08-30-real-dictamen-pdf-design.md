# Real Dictamen PDF Generation Design

## Goal

Replace the remaining demo PDF adapter with one production renderer that creates
institutional dictamen PDFs from the existing domain model, while making both
CREATE and UPDATE transactional with respect to destination selection.

The invariant is:

```text
no confirmed destination = no backend mutation
```

The implementation remains frontend-only. It does not modify the backend,
database, historical frontend, authentication, authorization, or centralized
HTTP recovery policy.

## Verified Starting Point

- Baseline: 479 passing tests on `main` commit `3599e74`.
- Production currently wires `DemoPdfGenerator`.
- `DictamenController.create()` already returns the final backend `Dictamen`
  plus a `PdfRequest`; the current UI does not generate or persist a PDF.
- The current update UI performs a real PUT but does not generate or persist a
  PDF.
- Flet 0.86.5 is installed. Its desktop `FilePicker.save_file()` can return a
  path before bytes exist. Web mode cannot provide that transactional ordering.
- `fpdf2` 2.8.8 is an approved production dependency and PyMuPDF 1.28.2 is an
  approved development dependency.

## Sources of Authority Reviewed

The design follows the task requirements first, then the current frontend
contracts, current reference PDFs and assets, and finally the historical
implementation.

### Current frontend

The relevant current contracts and flows were inspected in:

- `features/dictamenes/models.py`
- `features/dictamenes/pdf.py`
- `features/dictamenes/controller.py`
- `features/dictamenes/views/crear.py`
- `features/dictamenes/views/buscar.py`
- `infrastructure/http/reprobado_repository.py`
- `core/services.py`
- the corresponding controller, repository, view, and PDF tests

### Current references and assets

All three PDFs in `referencias/` were rendered and inspected. They are
single-page A4 documents using Helvetica/Helvetica Bold and the same three
embedded institutional images:

- `assets/ipn_logo.jpg`
- `assets/logo_esiqie.png`
- `assets/imagen_fondo.png`

The references establish the institutional hierarchy and styling, but also
show rigid-row and overlap defects that the new renderer must correct.

### Historical frontend

`The-C6H6/GESTION_ESCOLAR_FRONTEND`, branch `main`, exact file
`PDF/actions/crear_pdf.py`, was consulted read-only. Its institutional order,
copy, identity blocks, table concept, signature, and footer inform the design.
Its use of current time, direct file output, CWD/absolute paths, rigid cells,
magic pagination, and monolithic UI/filesystem coupling will not be copied.

### Current backend contract

`The-C6H6/GESTION_ESCOLAR_BACKEND`, branch `main`, was consulted read-only.
`ReprobadoResponse` includes:

- `Intentos_Ordinario: int`
- `MateriaInscrita: str | None`
- `InscritoActualmente: str | None`

`GET /reprobados` returns the complete `ReprobadoResponse` items. The current
frontend parser validates those fields but discards them when constructing its
domain model. The PDF requires `Intentos_Ordinario` and `MateriaInscrita`.
`InscritoActualmente` is not PDF data and will not be propagated into the PDF
domain.

## Approved Architecture

The selected architecture is a staged workflow:

```text
Flet view
  -> local validation and authorization
  -> native destination selection
  -> DictamenController mutation
  -> DictamenController -> PdfGenerator
  -> PdfDocumentStore
  -> UI reconciliation
```

Generation and persistence remain separate:

- `RealPdfGenerator` knows FPDF, the institutional layout, and assets. It does
  not import Flet or write files.
- `LocalPdfDocumentStore` knows paths, collision handling, and exclusive local
  writes. It does not know Flet or domain rendering rules.
- Flet owns the native selector because destination selection is interactive.
- `DictamenController` remains the boundary between UI and `PdfGenerator`.

No additional application workflow service is introduced. Focused async view
helpers make the staged CREATE and UPDATE flows directly testable.

## Domain Contract Changes

`MateriaReprobada` will retain the backend values required by the PDF:

```python
intentos_ordinario: int
materia_inscrita: str | None
```

`MateriaElegible` will carry those same values after the existing eligibility
calculation. There will be no defaults that invent attempts or enrollment
status.

`ApiReprobadoRepository` will map:

- `Intentos_Ordinario` -> `intentos_ordinario`
- `MateriaInscrita` -> `materia_inscrita`

`InscritoActualmente` remains validated as part of the complete transport
contract but is not copied into `MateriaReprobada`, `MateriaElegible`, or
`PdfRequest`.

`MateriaInscrita` values `SI` and `NO` are displayed unchanged. The backend
schema still permits `None`; if it occurs, the PDF cell is blank rather than
inventing a value.

`PdfRequest.materias` remains a 0..N tuple and no redundant display flag is
added.

## Renderer

`RealPdfGenerator` will implement the existing async `PdfGenerator.generate()`
protocol and return:

```python
GeneratedDocument(
    filename=build_pdf_filename(request.dictamen),
    content=<real PDF bytes>,
    is_simulation=False,
)
```

FPDF output is produced in memory and converted to immutable `bytes`. The
renderer never writes a temporary or final file.

The canonical filename builder is a single pure function:

```text
{dictamen.boleta}_dictamen_{dictamen.fecha:%Y-%m-%d}.pdf
```

It uses `dictamen.fecha`, not `fecha_sesion` and not the current clock.

The institutional session paragraph is produced only by the existing
`build_session_paragraph(request.fecha_sesion)` helper. The director is always
`request.director`; no fallback or hard-coded director remains.

## Institutional Layout

The document is A4 portrait and reuses the current IPN logo, ESIQIE logo, and
background image without copying or downloading assets.

The first page preserves this hierarchy:

1. institutional logos and school heading;
2. document title and confidentiality block;
3. dictamen key and domain date;
4. student name and boleta;
5. shared regulatory/session paragraph;
6. bordered final dictaminacion;
7. optional subjects table;
8. director/signature block;
9. institutional footer.

Variable text uses measured wrapping. Student name, dictaminacion, director,
and subject names can grow vertically without overlapping later content.

### Subjects table

When `request.materias` is non-empty, the table has the four confirmed columns:

1. `Materia Desfasada`
2. `Periodo Reprobada`
3. `Intentos Ordinario`
4. `Inscrita`

Each row height is the maximum measured height required by its cells. Borders
use the computed row height, and text is wrapped without truncation.

When `request.materias == ()`, the renderer emits no table, no table header, no
placeholder, no empty row, and no reserved table space. Signature and footer
move upward naturally.

### Pagination

Page breaks depend on measured remaining space rather than subject count.
Rows are indivisible. Before drawing a row, the renderer checks the complete
row height plus reserved signature/footer space. A continuation page repeats a
compact institutional header and the table header. The signature block is kept
together and moves to a new page when required. Footers never collide with
body content.

### Spanish Unicode

The renderer uses Helvetica/Helvetica Bold with the supported Latin character
encoding used by the references. Tests cover uppercase and lowercase accented
vowels, `Ñ`, `ñ`, and `ü`, including text extraction from the resulting PDF.

## Asset Resolution

Production constructs the renderer with an injected assets directory resolved
from module location, not from process CWD and never from an absolute machine
path. Tests can inject a controlled asset directory. Missing or unreadable
required assets produce a safe PDF-generation error.

The same resolver can be used by Flet startup so the application and renderer
agree on one existing asset directory without duplicating images.

## Destination Selection and Persistence

Desktop uses the installed Flet 0.86.5
`FilePicker.save_file(file_name=..., file_type=CUSTOM,
allowed_extensions=["pdf"])` API without `src_bytes`. This returns the selected
path before any backend mutation.

The picker receives the canonical filename as its suggestion. A valid filename
changed by the user is respected. A missing `.pdf` suffix is normalized to
`.pdf`; another suffix or an invalid/nonexistent parent is rejected before
POST/PUT.

Web and mobile cannot produce the selected filesystem path before PDF bytes.
Their CREATE/UPDATE mutations are therefore blocked before the picker and
backend with a controlled message directing the user to the desktop app.
Read-only web workflows remain available.

`LocalPdfDocumentStore` resolves collision names against the actual selected
path:

```text
base.pdf
base_2.pdf
base_3.pdf
...
```

It uses an exclusive create operation rather than a check-then-overwrite write,
so a concurrent file creation cannot cause silent replacement. CREATE and
UPDATE call the same implementation. Existing files remain byte-for-byte
unchanged.

## CREATE Workflow

Within the existing create request gate:

1. require administrator authorization;
2. validate candidate, eligibility, dictaminacion, director, and session date;
3. block unsupported web/mobile execution;
4. open the destination selector with the canonical suggested filename;
5. on cancellation, return neutrally and release the gate;
6. validate the returned path;
7. call the existing create repository exactly once;
8. retain the final backend `Dictamen` and its `PdfRequest`;
9. update local workflow state so a later PDF failure cannot be mistaken for a
   failed backend create;
10. generate through the controller and the real generator;
11. persist through the shared document store;
12. show the final saved path and backend key.

Cancellation performs zero POST, zero PUT, zero generation, and zero write.

## UPDATE Workflow

The update editor adds required director and session-date inputs. Subjects are
not part of dictaminacion search/update responses, so the approved UPDATE PDF
request uses `materias=()`.

Within the existing shared search/update/delete gate:

1. require administrator authorization;
2. validate changed dictaminacion, director, and session date;
3. block unsupported web/mobile execution;
4. select and validate the destination;
5. on cancellation, return neutrally and release the gate;
6. call the existing update repository exactly once;
7. validate and retain the final backend `Dictamen`;
8. replace the row in the current page immediately with that final object;
9. build a `PdfRequest` from that object, the captured director/session date,
   and `materias=()`;
10. generate through the same controller/generator used by CREATE;
11. persist through the same document store;
12. show the final saved path.

Blank or unchanged dictaminacion is rejected before the selector and performs
zero PUT and zero PDF output.

## Failure Semantics

The request gate covers validation, picker, mutation, generation, collision
resolution, and write. It is released on success, cancellation, and every
error.

- Picker cancellation is a neutral pre-mutation result.
- Picker/path errors are pre-mutation failures and perform zero POST/PUT.
- Backend failures use the existing error/session mapping and produce no file.
- Generation or filesystem failure after a successful POST/PUT never retries,
  rolls back, deletes, or compensates the backend mutation.
- After a post-mutation failure, CREATE reports the created backend key and
  clearly states that the PDF was not saved. UPDATE keeps the final returned row
  committed in the UI and clearly states that only PDF output failed.
- A post-mutation failure is never reported as cancellation.

Authentication, `require_admin()`, single-flight refresh, and one exact replay
remain unchanged. The local workflow does not add mutation retries.

## Testing Strategy

All behavior is implemented test-first. Focused tests precede implementation
and full verification precedes every commit.

### Domain and HTTP mapping

- required `Intentos_Ordinario` mapping;
- optional `MateriaInscrita` mapping including `SI`, `NO`, and `None`;
- propagation through eligibility into `MateriaElegible`;
- continued validation but non-propagation of `InscritoActualmente`.

### Renderer

PyMuPDF validates real non-empty PDF bytes, `is_simulation=False`, filename,
text, page count, and geometry for:

- no subjects;
- one subject;
- several subjects;
- an extremely long subject;
- enough subjects for multiple pages;
- complete Spanish Unicode;
- request director;
- shared session date paragraph;
- domain date filename.

No-subject tests assert that table headers and reserved table pages are absent.
Long/multipage tests assert complete text, dynamic rows, repeated table headers,
and no row/signature/footer collisions.

### Persistence

Temporary directories verify base, `_2`, `_3`, unchanged existing bytes,
custom selected filenames, suffix validation, and exclusive collision handling.

### CREATE and UPDATE workflows

Recording collaborators verify:

- confirmed destination: one picker, one mutation, one generation, one write;
- cancelled destination: one picker and zero mutation/generation/write;
- generation/write failure after mutation: no mutation replay and reconciled UI;
- UPDATE generation uses the final backend object and `materias=()`;
- CREATE carries all four subject-table values;
- web/mobile blocking occurs before mutation;
- the request gate always releases and rejects double activation.

### Visual validation and smoke

Four deterministic PDFs are rendered to images and inspected against all three
current reference PDFs: normal, no subjects, very long subject, and multipage.
The comparison covers logos, hierarchy, margins, wrapping, borders, signature,
footer, and pagination.

Desktop smoke covers CREATE/UPDATE destination cancellation, PDFs with and
without subjects, custom/colliding filenames, and post-save UI messages. Web
smoke confirms the controlled pre-mutation block. Mutations beyond the approved
smoke data require explicit user approval.

## Documentation and Removal

After the real adapter is wired, all `DemoPdfGenerator` references are audited.
If no test-owned need remains, its module and obsolete tests are deleted.
README, architecture documentation, and NOTES are updated only from verified
behavior and final observed results.

## Non-Goals

- No backend, database, or historical repository changes.
- No new API endpoints or PDF-specific HTTP queries.
- No persistent token or credential storage.
- No web mutation that violates destination-before-mutation ordering.
- No silent overwrite, automatic rollback, or mutation retry.
- No push, merge, tag, or worktree removal without explicit authorization.
