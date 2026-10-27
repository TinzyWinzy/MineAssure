# Local operation and deployment gates

## Start and inspect

Use `pwsh -File scripts/start-local.ps1` after the prerequisites in [local development](local-development.md). Native PostgreSQL, API, worker and Vite bind to loopback; development credentials live in ignored `.local/config.json`. Inspect `.local/*-error.log` and `/ready`. Stop with `pwsh -File scripts/stop-local.ps1`; local database files remain. Docker is bypassed in the current workflow. The retained Compose configuration is an optional unverified alternative.

Set secrets in a secret manager for any authorized hosted deployment and remove seeded credentials from hosted environments.

## Backup and restore rehearsal

Run `apps/api/.venv/Scripts/python.exe scripts/backup-local.py`. It uses a read-only repeatable-read transaction and exported snapshot for pg_dump, restores into a new uniquely named native database, and compares all public-table counts. The archive hash, path, restore name and counts are recorded in `.local/backup-report.json`. The source is not overwritten; archives and rehearsal databases are retained. See [verification evidence](verification-delivery.md).

This checks snapshot counts, not every field or a production recovery objective. Encrypt archives, restrict access, store off-site, capture recovery timings and rehearse on an isolated host before real customer use. The older Docker backup script is retained for that optional environment.

## Customer deployment gates

- Approve hosting jurisdiction, privacy/data-use terms, supported pricing/tax policy, financial delegation and source-verification owner.
- Configure an externally verified identity provider and MFA. Development login must fail closed outside development.
- Configure TLS, safe CORS, session lifecycle, bounded requests/rate limiting, managed secrets, least-privilege database/service accounts and RLS policies.
- Complete document quarantine/scanning, private storage and authorized signed retrieval before accepting customer documents.
- Implement/test durable background import with retry, idempotency and crash recovery before larger workloads.
- Review append-only audit protection, backup encryption, restore evidence, retention, incident response and observability.
- Run golden, cross-tenant/site/IDOR, concurrency, approval, export, accessibility, performance and customer UAT gates on the intended deployment.

No production deployment, ERP write-back, bank interaction, Anaplan connection or live telemetry integration has been performed. Such actions require explicit authorization and an assessed environment.
