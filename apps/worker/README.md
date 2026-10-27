# Background reconciliation worker

The worker runs from the API package so migrations, models and financial policy match:

```sh
cd apps/api
python -m app.worker
# Single polling iteration:
python -m app.worker --once
```

Set the same DATABASE_URL, ENVIRONMENT and SECRET_KEY as the API. Native Windows startup starts this process automatically; see [local development](../../docs/local-development.md).

Implemented: scoped immutable invoice identity, actor reauthorization, PostgreSQL SKIP LOCKED claims, expiring lease tokens, three-attempt retry/dead-letter state, atomic reconciliation/completion, replay-safe run identity and visible failures. Tests in apps/api/tests/test_jobs.py exercise stale owners, interrupted transactions, retries, changed input and revocation.

This worker processes reconciliation only. Large-file import, XLSX mapping and binary quarantine/scanning remain outstanding. The earlier placeholder Dockerfile is unused.
