# Native Windows development (no Docker)

The default local workflow uses PostgreSQL 16, Python 3.12+, Node 22+ and PowerShell 7+. It does not start Docker, WSL or a Windows database service. The cluster binds only `127.0.0.1:55432`. Development and test databases are separate. Only synthetic data is seeded.

## First setup

Download the PostgreSQL Windows binary archive from [EDB](https://www.enterprisedb.com/download-postgresql-binaries), linked by [postgresql.org](https://www.postgresql.org/download/windows/). Extract its `pgsql` directory under `.local/` in the repository. This checkout uses `postgresql-16.15-1-windows-x64-binaries.zip`. The runtime needs `pgsql/bin`, `pgsql/lib` and `pgsql/share`; pgAdmin and StackBuilder are unnecessary. Alternatively pass `-PgBinPath 'C:\Program Files\PostgreSQL\16\bin'` to `start-local.ps1`.

From the repository root:

```powershell
python -m venv apps/api/.venv
apps/api/.venv/Scripts/python.exe -m pip install -e './apps/api[dev]'
Push-Location apps/web
npm ci
Pop-Location
pwsh -File scripts/start-local.ps1
```

If dependencies and PostgreSQL binaries are already present, only the final command is needed. The script initializes a cluster once, generates local credentials, starts PostgreSQL, creates `mineassure` and `mineassure_test`, applies migrations, seeds development personas, and starts API, worker and Vite as hidden background processes. Existing cluster data is retained.

- App: http://localhost:5173
- API: http://127.0.0.1:8000/docs
- Readiness: http://127.0.0.1:8000/ready
- Sign-in: `ap@demo.local` / `demo`; finance: `finance@demo.local` / `demo`.
- Evidence: `verifier@demo.local` registers; `verifier2@demo.local` attests.
- Contracts: `preparer@demo.local` drafts; `approver@demo.local` approves.
- Administration: `admin@demo.local` / `demo`, then Settings.

All `.local` contents are ignored by Git: binaries, credentials, database files, process IDs and logs. Keep this directory private to the Windows account. These accounts are for local development only. No hosted identity provider is configured.

## Verify and stop

```powershell
pwsh -File scripts/verify-local.ps1
pwsh -File scripts/stop-local.ps1
```

Verification targets only `mineassure_test`: backend lint/format, migrations and drift, PostgreSQL tests, then frontend lint/build. Test databases must end `_test`. Pure engine tests also run without PostgreSQL: `apps/api/.venv/Scripts/python.exe -m pytest apps/api/tests/test_engine.py -q`.

Stopping checks recorded process start times before termination, then stops this cluster. Data remains. If startup fails, inspect `.local/api-error.log`, `worker-error.log`, `web-error.log` and `postgres.log`. Stop before changing ports. Use `-DatabasePort`, `-ApiPort` and `-WebPort` for a fresh checkout if defaults are occupied. Do not delete `pgdata` to resolve a port conflict.

## Background reconciliation

The UI submits `/api/v1/jobs/reconciliation` and polls the scoped job. The worker uses PostgreSQL `FOR UPDATE SKIP LOCKED`, a five-minute claim and three-attempt retry bound. Reconciliation and job completion commit atomically. A crash before commit rolls back the run and allocations; expired claims can be replayed. Actor grants are rechecked at execution. Terminal errors remain visible; a new request key permits an explicit retry.

Invoice identity is frozen at submission. Approved terms and attested evidence are selected at execution and retained in the immutable reconciliation snapshot. CSV imports retain their 256 KiB / 500 row limit. Large-file import and document scanning are separate outstanding capabilities.

## Additional release checks

With the native services running, execute `npm run test:e2e` from apps/web for browser/axe checks. From the root, run `apps/api/.venv/Scripts/python.exe scripts/benchmark-persistence.py` for the isolated 1,000-line measurement and `apps/api/.venv/Scripts/python.exe scripts/backup-local.py` for snapshot-consistent restore rehearsal. Backup artifacts and restore databases are retained; no source tables are overwritten.
