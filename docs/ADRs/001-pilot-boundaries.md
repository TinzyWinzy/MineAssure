# ADR-001: Controlled equipment-hire pilot

Status: accepted for local synthetic demonstration, 25 October 2026.

## Context

The existing system had a pure Decimal rule engine, relational models and an unfinished UI. The engineering review identifies financial allocation, evidence, authority and reproducibility as critical controls. A distributed redesign would add operational uncertainty without addressing those controls.

## Decision

Keep React/Vite and FastAPI in one monorepo with PostgreSQL as the transactional source of truth. Use immutable approved contract inputs, explicit attested evidence, deterministic run results, distinct human approval and approved-only file exports. Expose versioned REST routes and use Alembic for schema changes. Restrict the supported pricing policy to USD hourly hire and synthetic records.

## Consequences

The deployment is understandable and locally reproducible. PostgreSQL row locking is required for allocation concurrency; an SQLite test cannot prove that guarantee. External identity, MFA, RLS, private document storage, malware scanning, persisted background processing, restore rehearsal and customer UAT remain independently verified release gates. The presence of model tables or compose service definitions is not evidence those workflows work.
