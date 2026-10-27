# MineAssure

Mining contractor invoice assurance for Nexus Agronomics. Compare invoices with approved hourly contracts and attested work, investigate exceptions, record distinct human approvals and export approved costs with provenance. All included fixtures are synthetic.

Release status: local demonstration under verification. See [implementation status](docs/implementation-status.md) for actual checks and outstanding gates. Production identity, private document handling and customer deployment approval are required before using client data.

## Run the synthetic demo

Use the native Windows setup in [local development](docs/local-development.md). After installing the documented Python, Node and PostgreSQL dependencies, run from this directory:

```powershell
pwsh -File scripts/start-local.ps1
```

This starts a project-local PostgreSQL instance, applies migrations, seeds the demonstration and starts API, reconciliation worker and web. No external service or real customer account is needed. Ports are bound to loopback. Docker is optional and bypassed in the current workflow.

- App: [localhost:5173](http://localhost:5173)
- API/OpenAPI: [localhost:8000/docs](http://localhost:8000/docs)
- Database readiness: [localhost:8000/ready](http://localhost:8000/ready)

Inspect `.local/*-error.log` for startup problems. Verify with `pwsh -File scripts/verify-local.ps1` and stop with `pwsh -File scripts/stop-local.ps1`; database files remain. Native credentials are generated into ignored `.local/config.json`. The native database listens on port 55432. The retained Compose configuration is an optional alternative and has not been verified in this revision.

## Development-only personas

Password for all synthetic accounts: `demo`. Login is restricted to development configuration. Do not expose these credentials or this Compose environment to a public network.

| Email | Role |
| --- | --- |
| `admin@demo.local` | Tenant administrator |
| `preparer@demo.local` | Contract preparer |
| `approver@demo.local` | Contract approver |
| `verifier@demo.local` | Operations verifier |
| `verifier2@demo.local` | Independent operations verifier |
| `ap@demo.local` | AP analyst |
| `finance@demo.local` | Finance approver |
| `auditor@demo.local` | Auditor |
| `partner@demo.local` | Partner read-only |

The seed organization is `org-demo`, site `site-1`, contractor `ctr-1`, contract `contract-1`, work code `EQ-HIRE`, USD $240/hour. Roles are distinct; an administrator account does not substitute for a finance decision.

## Demonstration flow

Use [the walkthrough](docs/demo-walkthrough.md) and [UAT checklist](docs/UAT-checklist.md). The central fixture is 160 hours at $250 = $40,000 invoiced versus 145 independently attested hours at $240 = $34,800 provisionally supported. Quantified variance is $5,200 once. A separate missing-evidence invoice remains $2,400 unverified and cannot be approved as supported.

Sample CSVs and their limits are documented in [import schema](docs/import-schema.md). API clients can inspect exact endpoint schemas through OpenAPI. The Files workspace supports staged CSV/XLSX upload, column mapping, preview, validation, atomic ingestion and downloadable source/processed/error outputs (2 MiB / 500 rows). Large asynchronous ingestion and document quarantine remain outstanding. See [operating workflows](docs/operating-workflows.md) for CRUD, associations and mathematical outcomes.

## Develop and verify locally

The existing Python virtual environment is at `apps/api/.venv` on this checkout. For a fresh environment, create a Python 3.12+ virtual environment, activate it, then install the API with development dependencies:

```sh
cd apps/api
python -m venv .venv
# Windows PowerShell: .\.venv\Scripts\Activate.ps1
# POSIX shell: source .venv/bin/activate
python -m pip install -e '.[dev]'
python -m alembic upgrade head
python seed.py
python -m uvicorn app.main:app --reload --port 8000
```

Use a disposable PostgreSQL database and set `DATABASE_URL` before running tests; the local default targets `mineassure` on port 5432. Never run tests against customer or production data. In another terminal:

```sh
cd apps/web
npm ci
npm run dev
```

Checks:

```sh
# apps/api with the Python environment active
python -m pytest -q
python -m ruff check .
python -m alembic check
# apps/web
npm run lint
npm run build
```

Read CI and the implementation-status report for the test database setup and any checks not yet executed. Tests on SQLite alone do not establish PostgreSQL allocation locking behavior.

## Repository guide

```text
apps/api/          FastAPI, deterministic engine, policy, persistence, migrations, seed, tests
apps/web/          React + TypeScript interface
apps/worker/       Worker usage; implementation shares apps/api/app/worker.py
docs/             Source PRD/SAD, decisions, financial semantics, threat model, UAT, examples
scripts/          Windows demo startup and non-destructive backup/restore rehearsal
docker-compose.yml  Local synthetic stack
```

[Financial semantics](docs/financial-semantics.md) explains the amount categories. [Threat model](docs/threat-model.md) and [deployment runbook](docs/security-deployment-runbook.md) list required production controls and backup procedure. The [requirements matrix](docs/requirements-test-matrix.md) records traceability and remaining limitations. No ERP, payment, Anaplan or mine telemetry integration is connected.
