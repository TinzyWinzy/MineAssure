# MineAssure implementation status

Updated: 26 October 2026. Release: **verified synthetic local pilot; not a production release**.

## DONE — implemented local pilot

- React/TypeScript interface: sign-in, scoped site selection, dashboard/drill-down, contractors, contracts, immutable version history and revision drafting, evidence registration/import/independent attestation, invoice input/import/review, investigations/comments, finance approvals, immutable exports, audit and site/user administration.
- Server-derived identity with fresh tenant/site/role grants, independent contract/evidence/finance decisions, USD 50,000 per-line finance authority, stale-version rejection, live membership revocation and fail-closed hosted configuration.
- Effective approved USD hourly terms, Decimal arithmetic and separate supported, unverified, quantified variance and approved categories. Golden A: $40,000 = $34,800 supported + $5,200 variance. Missing evidence remains unverified and cannot be approved.
- PostgreSQL allocation locking, frozen reconciliation snapshots/hashes, supersession/release, immutable decisions, partial approval, export idempotency and artifact hash verification. Malformed or legacy provenance is quarantined.
- Durable reconciliation worker: scoped jobs, immutable invoice input identity, execution-time authorization, SKIP LOCKED claims, lease tokens/expiry, three-attempt retry bound, atomic reconciliation/completion, crash recovery and dead-letter status. UI polls job progress.
- Draft CRUD for suppliers, contract terms, unattested evidence and unassessed invoices, including line add/edit/remove and contract associations. Revision conflicts, finalized history and referenced deletions are protected and audited.
- Files workspace: staged CSV/XLSX upload, column mapping, preview, row/field validation, atomic commit, created-record associations and original/processed/error downloads. Original bytes/checksum and input lineage are retained. Separate independent verifier account included.
- Mathematical outcomes: explicit formula steps, amount conservation, frozen invoice/contract/evidence sources, verifier and review provenance, linked-record navigation and CSV/JSON outcome reports.
- Native Windows PostgreSQL/API/worker/web startup, stop and verification scripts. Docker is bypassed per user direction; retained Compose configuration is optional and unverified in this revision.
- Native snapshot-consistent backup/restore rehearsal, measured persisted reconciliation benchmark, refreshed OpenAPI, example inputs, financial semantics, threat model, UAT and deployment documentation.
- CI configuration includes backend checks, frontend build and Playwright finance/admin/mobile accessibility/file-processing/CRUD journeys. Hosted CI has not been executed in this workspace.

## Verified commands and actual results

| Check | Result |
| --- | --- |
| `pwsh -File scripts/start-local.ps1` | Native PostgreSQL 16.15, migrations through 0006, seed, API, worker and web started; readiness confirmed. |
| `pwsh -File scripts/stop-local.ps1`, then start again | Passed: recorded process trees stopped, database retained and services restarted. Repeated startup reused running processes. |
| `pwsh -File scripts/verify-local.ps1` | Passed: backend Ruff lint/format, Alembic upgrade/drift, engine mypy, 126 PostgreSQL tests, frontend lint/build. |
| `pytest` portion of verification | **126 passed**, one upstream Starlette/httpx deprecation warning. Includes golden financial cases, RBAC/IDOR/SoD, concurrent allocation, concurrent worker claims, retry/replay, revocation and immutable export tests. |
| `npm run test:e2e` | **5 passed**: file upload/mapping/ingestion → invoice edit → evidence links → mathematical output; supplier/invoice CRUD; independent evidence → queued assessment → partial finance approval/export; mobile WCAG A/AA axe smoke checks and no page overflow; site/user provisioning and revocation. |
| `python scripts/benchmark-persistence.py` | 1,000 persisted lines in **11.8475 s**. Includes rate/evidence queries, locks, allocations, snapshots, findings/cases and output. Excludes fixture ingestion and network HTTP. Benchmark data rolled back. |
| `python scripts/backup-local.py` | Passed: snapshot-consistent dump restored into a separate native database; all **26 table counts matched**. Source database unchanged. |
| `python scripts/export-openapi.py` | Refreshed `docs/openapi.json` with implemented routes. |
| `npm install` audit | 0 frontend vulnerabilities reported at installation. No full backend vulnerability audit is claimed. |

Backup identifiers and exact reference environment are in `verification-delivery.md`. Start, verify and stop instructions are in `local-development.md`.

## PARTIAL — remaining master-build requirements

- Production OIDC/SSO/MFA and customer-specific approval/delegation configuration are not implemented. Development auth is disabled outside development/test.
- Application tenant/site checks are tested; PostgreSQL RLS and composite database isolation constraints are not implemented.
- The staged file workflow supports CSV/XLSX up to 2 MiB / 500 rows, with column mapping. XLSX uses the first worksheet and reviewed values only. Durable large-file ingestion remains outstanding; the worker handles reconciliation. The older one-step CSV endpoint retains its 256 KiB limit.
- Binary document quarantine, malware scanning, private storage/signed retrieval and complete review bundles remain outstanding.
- Cases support findings and comments. Full assignment/dispute/override/appeal/reversal policy, customer fuzzy duplicate detection and partner dataset sharing are not implemented. Decided invoices require a separately implemented reversal workflow before rerun; partners are denied general datasets.
- Contract revisions support effective-dated USD hourly rates and per-line caps. Other currencies, tax, aggregate-period caps, minimum/standby and approved variation pricing require additional policy and tests.
- Type checking passes for the pure engine and frontend. Whole-backend mypy still reports legacy SQLAlchemy Column typing and optional-value errors; no claim of full backend typing is made.
- API pagination exists for key resources; some lists remain bounded. Broad automated UI coverage, load/soak testing and a full accessibility audit beyond the tested journeys remain outstanding.

## NOT STARTED — external/customer release gates

Production hosting approval, identity-provider provisioning, customer data-use permission, jurisdiction/tax/pricing policy sign-off, independently trusted operational sources, retention/SLA/monitoring, encrypted off-site scheduled backups and measured production RPO/RTO. No ERP, payment, Anaplan or telemetry integration is connected. Customer UAT and independent production security review are not complete.

## CRUD and file-processing correction (26 October 2026)

The previous delivery lacked record edit/delete controls, staged file ingestion and visible calculation/source drill-through. These have now been implemented. See operating-workflows.md for the exact controls and workflow. The new backend tests cover allowed/stale/protected CRUD, edited-input separation of duties, XLSX/CSV mapping/atomic ingestion, output hashes, source associations, mathematical conservation and undetermined missing-evidence outcomes. Final browser results are recorded in verification-delivery.md.
