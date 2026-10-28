# Native delivery verification evidence

Executed on 25 October 2026 from the Windows workspace. Docker was bypassed at the user's direction after its runtime sockets prevented startup.

## Reference environment

Python 3.12.10; PostgreSQL 16.15; Windows 11 build 26300; Intel64 Family 6 Model 140 Stepping 1 (GenuineIntel). Native PostgreSQL binds only 127.0.0.1:55432. The development database is mineassure; automated backend tests use mineassure_test. Credentials are generated into ignored .local/config.json and are not included here.

Official EDB archive used: postgresql-16.15-1-windows-x64-binaries.zip, 332441502 bytes. Download SHA256: `25e6fcdfb8caec38691bf461125e7564508760666f7b8e5dc6a5f0818f58f81e`. This records the downloaded artifact; it is not an independently published vendor checksum. Only bin/lib/share runtime files were extracted under ignored .local/pgsql.

## Executed checks

- Native startup applied migrations through 0005, seeded synthetic data and started API, reconciliation worker and Vite; readiness succeeded.
- Native verify script passed Ruff lint/format, Alembic upgrade and drift (no upgrade operations), pure-engine mypy, **111 backend tests**, frontend lint and TypeScript/Vite build. Pytest reported one upstream Starlette/httpx deprecation warning.
- Playwright **3 passed** in 16.7 seconds against freshly restarted native services: independent evidence/queued assessment/partial approval/export/hash; mobile sign-in/dashboard axe WCAG A/AA with no violations and no page overflow; site/user creation and grant revocation. The audit found contrast/keyboard-scroll issues that were fixed before the passing run. This smoke coverage is not a complete accessibility certification.
- Native 1,000-line persisted reconciliation: **11.8475 seconds**, all lines yielded $34,800 supported and $5,200 variance with 1,000 active allocations. Fixture setup, file ingestion and network HTTP are excluded; financial query, locking, ledger, snapshot, finding/case and output work are included. All benchmark rows rolled back.
- OpenAPI regenerated from implemented FastAPI routes.
- Frontend npm audit at development dependency installation reported 0 vulnerabilities. Whole-backend mypy was attempted and has unresolved legacy ORM typing/optional-value errors; pure-engine mypy passes.

## Native backup/restore rehearsal

Command: `apps/api/.venv/Scripts/python.exe scripts/backup-local.py`.

Source was held in a read-only repeatable-read transaction; pg_dump used its exported snapshot. The custom archive was restored into a new database, and counts for all 26 public tables matched that snapshot. No source table was changed or removed.

- Archive (local, ignored): `backups/native-cedb141c9d3543a583ceac2a9b61a5ab.dump`
- SHA256: `b1cbcfb0bdd1590b502610e68325ed033c70e41bd494f56d2e60893f4d036321`
- Restored database retained: `restore_d5cc82d7c20c4fc392497294878011e7`
- Example matching counts: users 9; memberships 9; contracts 2; contract versions 2; evidence work records 2; invoices/lines 4 each; runs 6; results 6; findings/cases 14 each; allocations 4; jobs 3; audit events 19. Approvals and exports were still zero at the snapshot; later browser tests independently verified partial approval/export/hash.

This verifies local synthetic restore and table counts, not production recovery objectives or semantic equivalence of every field. Earlier Docker backup evidence belongs to a previous synthetic state and is superseded for this native workflow. No successful Docker build or hosted CI run is asserted.

Native stop/restart and repeated startup reuse were verified. Process start times are checked as timestamps, and the Windows virtualenv Python child process is stopped with its recorded process tree. Screenshots: `screenshots/native-approved-desktop.png` and `screenshots/native-overview-mobile.png`. The approved-cost CSV example is `examples/approved-costs.csv`.

## CRUD, ingestion, associations and mathematical outputs — 26 October 2026

The prior delivery had create/read workflows but lacked core edit/delete controls, staged file processing and visible formula/source drill-through. The correction adds:

- Revision-protected draft CRUD for suppliers, contract terms, unattested evidence and unassessed invoices, with invoice line editing, association changes, deletion confirmation and immutable-history guards. Edited-input contributors remain excluded from approving/attesting their own work.
- Staged CSV/XLSX processing with mapping, source preview, precise row/field errors (including blank-row numbering), atomic ingestion, repeat-upload/commit idempotency, preserved original bytes/hash, file lineage, and original/processed/error downloads.
- Related-record navigation from supplier to contracts/invoices, contract to evidence/invoices, and invoice/evidence to original input files and reconciliation history.
- Mathematical formula steps, conservation checks, frozen source/decision provenance, and CSV/JSON reports. Missing evidence is explicitly unverified with variance undetermined.

Executed against native PostgreSQL after migration 0006:

| Check | Actual result |
| --- | --- |
| Native verification script | Passed: 126 backend tests in 28.42 s, Ruff lint/format, no Alembic drift, pure-engine mypy, frontend lint and TypeScript/Vite build. One upstream Starlette/httpx deprecation warning. |
| Full browser suite after restart | 5 passed in 19.3 s. Includes upload → map → validate → ingest → edit invoice → reconcile → inspect evidence associations and formula results → download outcome CSV; supplier/invoice edit/delete UI; existing finance/export, mobile axe and admin workflows. |
| Edited-file arithmetic | 150 hours × USD 245 = USD 36,750 invoiced; 145 independently attested hours × USD 240 = USD 34,800 supported; USD 1,950 variance. Browser asserted those results and downloaded CSV with the same work reference and variance. |
| XLSX backend workflow | Mapped workbook preview/validation/commit, original-byte hash equality, processed output, independent-attestation state, idempotency and formula rejection passed. |
| OpenAPI | Regenerated with CRUD, ingestion and mathematical-output routes. |

Verified screenshot: `screenshots/file-ingestion-outcomes.png`. Usage guide: `operating-workflows.md`. Limits remain explicit: XLSX first worksheet, reviewed values, 2 MiB / 500 rows; no PDF/OCR or large asynchronous file ingestion is claimed. Production document storage/scanning, identity and customer deployment remain separate gates.

## Data hygiene and key custody - 28 October 2026

Scope: data classification, original-file purge, removal of the unimplemented scan flag, and separation of the signing-key encryption secret. Executed on Windows against native PostgreSQL 16 on port 5432 (test database `mineassure_test`).

| Check | Actual result |
| --- | --- |
| `pytest -q` | 138 passed in 420.66 s; one upstream Starlette/httpx deprecation warning. |
| `ruff check app tests` | All checks passed. |
| `ruff format --check app tests` | 42 files already formatted. |
| `alembic check` at revision 0010 | No new upgrade operations detected. |
| `mypy app/engine.py` | Success: no issues found in 1 source file. |
| `npm run lint` and `npm run build` | Passed; 28 modules transformed, bundle 286.39 kB (84.62 kB gzip). |
| Playwright journeys | Not rerun. A development stack already listening on 5173/8000 was running pre-change code; restarting it would disrupt the operator's running demo. |

New coverage: purge requires an imported batch and the tenant administrator role; purge is idempotent; original bytes are cleared while checksum, processed rows, record links and a single audit event remain; the source download returns 410. Production settings reject a missing signing secret and a signing secret equal to `SECRET_KEY`. Development keys encrypted before the change remain readable through the dev/test-only fallback.

Residual: no automatic retention schedule, no malware scanner, no database RLS, and signing keys remain under server-side custody. See `data-classification.md`.
