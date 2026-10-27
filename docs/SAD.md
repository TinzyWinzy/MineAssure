# MineAssure SAD — source transcription

Source: `MineAssure_SAD_v0.1.docx`. Extracted from the original document paragraphs; table and visual layout is not preserved. The master build prompt and engineering review take precedence where they conflict.

MineAssure — System Architecture Document

SAD v0.1 | Secure, Traceable Mining Invoice Assurance

NEXUS AGRONOMICS  |  MineAssure  |  v0.1  |  25 October 2026

Status: Draft for internal review and partner discovery. All sample values and commercial assumptions are illustrative.

1. Architecture overview

MineAssure is a modular web application for reconciling mining contractor invoices against contracts and operational evidence. The first deployment is a modular monolith with background workers, a relational database and private document storage; boundaries permit extraction into services if scale or compliance later warrants it. The deterministic assurance engine owns financial computations, while humans own acceptance and payment readiness decisions.

2. Architecture drivers and design principles

Explainability first: every result identifies precise inputs, applicable contract version, rule version and calculation trace.

Tenant isolation and least privilege on every data access path, including exports and background jobs.

No AI-generated financial decisions; optional extraction assistance must require validation and preserve originals.

Idempotency for imports, reconciliation and exports; use immutable run snapshots for reproducibility.

Financial correctness via decimal data types, units of measure, effective dates, tolerances and explicit rounding.

Integrations are read-first and file-based in MVP, moving to controlled external APIs only with customer permission.

3. Logical context and components

Component

Responsibility

Technology (proposed)

Web UI

Dashboard, contract/evidence/invoice workflows, review queue and audit views

React + TypeScript + Vite

API / policy layer

Authentication, tenant/site scope, authorisation, request validation, audit events

Python FastAPI

Contract domain

Effective-dated contract snapshots, rate schedule and variations

Python service module

Evidence domain

CSV/XLSX mappings, operational records, file metadata and provenance

Python service module + object storage

Assurance domain

Line matching, decimal calculations, rule engine and findings

Python pure domain functions

Case/approval domain

Review transitions, segregation of duties, threshold approvals

Python service module

Reporting/export domain

KPIs, reviewed actuals, CSV and evidence package exports

Background jobs and SQL views

Persistence

Transactional store with tenant/site keys and immutable run metadata

PostgreSQL / managed Supabase

Job queue

Asynchronous imports/reconciliations with retries and dead-letter tracking

Queue + worker, selected at implementation

4. Architecture diagram (logical flow)

Mine operator / finance browser → React UI → FastAPI authenticated API → {Contracts, Evidence, Invoices, Assurance, Case Management, Reporting} → PostgreSQL + Private Object Storage. Background job worker consumes versioned import and reconciliation tasks. External sources feed validated CSV/XLSX now; ERP/Anaplan adapters are phase 2. All writes produce append-only audit events.

5. Trust boundaries, deployment and network

Public edge: HTTPS terminates at managed gateway; APIs enforce auth and bounded request sizes; no direct database exposure.

Application: API and worker run with distinct service identities; worker permissions restricted to its job domain.

Data: private PostgreSQL, encrypted backups and private object bucket; signed short-lived file access after policy checks.

Tenancy: tenant_id and site_id mandatory on business records, supported by database RLS where available plus application policy tests.

Admin: MFA, minimal production access, separate staging and production projects, audited privileged actions.

Deployment: managed frontend, containerised FastAPI and worker, managed PostgreSQL/object storage; infrastructure-as-code where practical.

6. Domain data model

Entity / table

Keys and required relations

Notes

organisations, sites, memberships

org_id; site.org_id; membership.user_id/org_id

Enforce tenant/site permissions.

contractors

contractor_id, org_id, site assignment

Supplier identity normalization.

contracts, contract_versions

contract_id; version_id, valid_from/to

Immutable approved version; draft editing separately.

contract_rate_lines, variations

version_id, work_code, unit, decimal_rate, dates

Overlap constraints; approved variation references.

operational_records, evidence_files

org/site, contractor, work_code, dates, unit, quantity

Source checksum, verifier and confidence state.

invoices, invoice_lines

invoice_id, vendor ID, period, amount; line keys

Tax mode and invoice fingerprint.

reconciliation_runs, rule_results

run_id, input_snapshot_hash, rule_set_version

Deterministic trace per invoice line.

exceptions, review_decisions

exception ID; state transitions, approver

Append-only decisions; no in-place history edits.

audit_events, export_batches

actor, action, object, timestamp, correlation ID

Write-once application log + backup policy.

Amounts: NUMERIC(20, 6) for intermediate rates/quantities (adapt precision to domain), NUMERIC(20, 2) for settled minor-unit USD amounts where appropriate. Store currency ISO code and rounding policies per contract. Temporal data uses UTC timestamps plus site local date/shift boundaries. Do not use floating point for monetary data.

7. Ingestion and validation design

Import request creates job with tenant/site identity, mapping version, uploader and idempotency key.

Upload original file to private object storage; record checksum, MIME, byte size and scanning result.

Parse to staging rows. Validate required columns, foreign keys, units, numeric scales, duplicated source IDs, dates and amount consistency.

Present rejected rows and unmapped codes. Only accepted, reviewed batches are committed to the canonical tables.

Operational records require declared source and verifier; unverifiable records remain visible but are not counted as independently supported evidence.

Re-import of the same data is detected by source identity and idempotency constraints, not just filename.

8. Reconciliation algorithm and rule lifecycle

Algorithm: (1) freeze invoice lines and evidence references; (2) resolve contractor/work code/period mappings; (3) select approved contract version and variations effective on service date; (4) normalize units; (5) compute contract-supported quantity and rate; (6) execute configured rule set; (7) de-duplicate monetary exposures and produce line result, exceptions and trace; (8) persist immutable run and hashes; (9) route for human review.

Missing evidence is not interpreted as zero delivered work. It yields an “unverified” outcome; monetary support may be undetermined. Where overlapping rule findings exist, overall potential exposure uses a single payable comparator and does not sum duplicate warnings. Tax, retention, standby and escalation are deliberately excluded until models are formally specified.

State / status

Permitted transition

Invoice

draft → validated → reconciled → under_review → approved_partial/approved_full/disputed

Exception

open → investigating → resolved_accepted/resolved_adjusted/disputed/closed_no_issue

Reconciliation run

queued → running → completed/failed/superseded

Contract version

draft → pending_approval → approved → superseded/expired

All state transitions require authorisation, optimistic concurrency protection and audit entry. Rerunning after new evidence creates a new run; previous run remains available.

9. API surface (indicative REST v1)

Method and path

Use

POST /v1/contracts; GET /v1/contracts/{id}

Create and inspect scoped contracts.

POST /v1/contracts/{id}/versions/{versionId}/approve

Dual-approve effective rate version.

POST /v1/imports; GET /v1/imports/{id}

Initiate and inspect validated data jobs.

POST /v1/invoices; GET /v1/invoices/{id}

Create/read invoice with line evidence.

POST /v1/invoices/{id}/reconciliations

Request idempotent rule execution.

GET /v1/reconciliations/{id}/results

Retrieve findings, provenance and rule traces.

PATCH /v1/exceptions/{id}

Record role-authorised case action with version precondition.

POST /v1/exports/approved-costs

Generate export of reviewed/approved data.

GET /v1/audit-events?object_id=...

Retrieve restricted audit history.

Security controls: OpenAPI schema, scoped authorisation on every endpoint, UUID opaque IDs, restrictive CORS, request/rate limits, validation, pagination, idempotency-key header on mutations, version/ETag handling on approval transitions.

10. Roles, threat model and mitigations

Threat

Control

Cross-tenant document or object leak

RLS + API policy + presigned URL check + isolation tests.

Invoice or evidence tampering

Original object checksum, immutable version references, event audit.

Privilege escalation / self-approval

Fine-grained RBAC, distinct approver and preparer on sensitive approvals.

Malicious document uploads

Content-type checks, size caps, malware scan, isolated parsing workers.

Duplicate jobs/payments

Idempotency keys, unique constraints and manual payment control outside system.

Credential theft

MFA for privileged access, secret manager, rotation and alerting.

Uncontrolled integration access

Least-privilege service accounts, read-only by default, customer approval.

Logging private data

Redact secrets/PII, avoid file content in logs, restrict log retention.

11. Reporting, auditability and operational telemetry

Dashboards aggregate only eligible invoice states and reconcile to detail-level totals. Maintain separate financial categories: invoiced; evidence-supported (provisional); reviewer-approved; disputed; unverified; confirmed adjustment/recovery. Never label potential exposure as “savings”. Include denominator, currency, site and reporting window.

Telemetry: job completion/error rate, import validation failures, reconciliation processing time p50/p95, rule precision confirmed in review, backlog by age, permission denials, export history, storage growth and backup/restore success.

12. Integration contracts and Anaplan option

MVP: export approved invoice-line actuals as versioned CSV with org/site, contractor, work code, service period, amount, currency, adjustment reason and source IDs. A manual upload to an authorised planning model is the first partner demonstration path. Phase 2 may implement authenticated Anaplan imports via an approved integration account and a documented dimension mapping; no direct integration is assumed.

13. Test strategy and acceptance gates

Test class

Mandatory tests

Unit/golden cases

Rates, date boundaries, unit conversion, tolerances, contract amendments, decimal rounding.

Property-based

Nonnegative quantities, no duplicated exposure, deterministic re-runs for frozen inputs.

Integration

Staging import, row rejects, object integrity, job retry/idempotency, export totals.

Security

Cross-org and cross-site denial, IDOR, role escalation, self-approval, signed URLs.

Performance

Benchmark 1,000 invoice lines/60s on representative deployment; publish actual result.

Resilience

Database backup/restore, worker crash recovery, partial import rollback.

UAT

One complete contract-to-export scenario verified by operations and finance reviewer.

14. Delivery plan and ADRs

Phase

Outputs

1. Weeks 1–2

Repo scaffolding, schema migrations, authentication/roles, contract and evidence fixtures.

2. Weeks 3–4

File ingestion, invoice data, decimal rule evaluation and golden fixtures.

3. Weeks 5–6

Exception lifecycle, approval workflow, audit trails, reviews and permissions.

4. Weeks 7–8

Dashboard, export, security hardening, observability, demo and pilot UAT.

5. Weeks 9–10 optional

Data mapping and remediation, scale test, restore exercise and deployment gate.

ADR-001 Modular monolith over microservices (small-team operability). ADR-002 PostgreSQL transactional source of truth. ADR-003 Deterministic rules and human adjudication. ADR-004 Immutable reconciliation snapshots. ADR-005 File-based financial export before external write-back. ADR-006 Tenant/site authorisation at application and database layer.

15. Open architecture decisions

Select the pilot pricing model (time-based machinery, tonne hauled or drilling metres) and contractual edge cases.

Agree expected source data formats, actual verified source of truth, timezone, currency, and tax treatment.

Choose identity provider and whether clients require SSO, MFA for all users, and geographic hosting restrictions.

Confirm retention periods, third-party data-sharing permissions and partner access model.

Confirm business continuity, availability SLA and RPO/RTO with operator sponsor.

Determine whether 163 Solutions will only model/export data or also resell and support the product.
