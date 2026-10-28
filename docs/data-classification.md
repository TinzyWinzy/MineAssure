# Data classification and retention

Updated 28 October 2026. Applies to the synthetic pilot database and to any future
customer deployment. All current fixtures are synthetic.

Classification levels:

| Level | Meaning | Handling |
| --- | --- | --- |
| **C1 Public** | Safe to publish | No restriction |
| **C2 Internal** | Operational metadata; low harm if disclosed | Authenticated tenant access only |
| **C3 Confidential** | Commercial terms, identities, free text | Tenant-scoped, no external sharing without approval |
| **C4 Financial-restricted** | Amounts, approvals, signatures, audit trail | Tenant-scoped, append-only, retained for audit |
| **C5 Secret** | Credentials, private keys, session material | Never returned by any API; separate encryption key |

Data is classified by field, not by screen. A single table can mix levels.

## Stored data

### Identity and access (`organisations`, `sites`, `users`, `memberships`)

| Field | Level | Notes |
| --- | --- | --- |
| `organisations.name`, `sites.name` | C2 | Tenant and site labels |
| `users.email` | C3 | Work email; unique login identifier |
| `users.hashed_password` | C5 | bcrypt hash, never returned |
| `users.is_active` | C2 | Access state |
| `memberships.role`, `site_id` | C2 | Current authorization source; re-read per request |

### Commercial terms (`contractors`, `contracts`, `contract_versions`, `rate_lines`, `contract_variations`)

All C3; approved terms and content hashes are C4 because they determine payable amounts.

| Field | Level | Notes |
| --- | --- | --- |
| `contractors.name` | C3 | Supplier identity |
| `contracts.title`, dates | C3 | Scope description |
| `contract_versions.status`, `approved_by`, `approved_at`, `content_hash` | C4 | Immutable approval evidence |
| `rate_lines.rate`, `cap_hours`, `minimum_hours`, `standby_rate` | C4 | Effective pay terms |
| `contract_variations.description`, `rate_delta` | C3/C4 | Free text; amount delta is C4 |

### Evidence (`work_records`, `evidence_allocations`)

| Field | Level | Notes |
| --- | --- | --- |
| `work_reference`, `work_code`, `service_date`, `quantity`, `unit` | C3 | Operational attestation |
| `status`, `attested_by`, `attested_at`, `created_by`, `revision` | C4 | Independent verification chain |
| `evidence_allocations.quantity`, `status` | C4 | Prevents double-counting |

### Invoices (`invoices`, `invoice_lines`)

All C4 except free-text description (C3).

| Field | Level | Notes |
| --- | --- | --- |
| `supplier_invoice_no`, `period_start`, `period_end` | C3 | Supplier billing reference |
| `quantity`, `unit_price`, `amount`, `work_reference` | C4 | Payable amounts |
| `description` | C3 | Free text from the supplier; unredacted |
| `fingerprint` | C2 | Duplicate detection only |

### Uploaded files (`import_batches`)

| Field | Level | Notes |
| --- | --- | --- |
| `source_bytes`, `source_text`, `normalized_json` | C3/C4 | Original customer file contents; may contain any supplier text |
| `mapping_json`, `errors_json` | C2 | Processing metadata; row errors can echo cell values |
| `sha256`, `filename`, `status`, `purged_at`, `purged_by` | C2 | Retained after purge for lineage |

Original bytes are retained until an authorised administrator purges the batch
(see [operating workflows](operating-workflows.md)). Purge keeps the checksum,
normalised rows, errors, created-record links and audit event; it removes the
original file content. Staged or validated batches cannot be purged because they
are still being worked on.

### Assessment artefacts (`reconciliation_runs`, `reconciliation_line_results`, `findings`)

All C4.

| Field | Level | Notes |
| --- | --- | --- |
| `input_snapshot` | C4 | Frozen copy of invoice, contract and evidence at run time |
| `input_hash`, `rule_set_version` | C2 | Reproducibility identifiers |
| `invoiced_amount`, `supported_amount`, `unverified_amount`, `quantified_variance`, `approved_amount` | C4 | Amount categories; never collapsed into a single "saving" |
| `explanation`, `evidence_refs` | C3 | Human-readable rule output |
| `findings.message`, `quantified_amount` | C3/C4 | Rule warnings; not additive exposure |

### Human decisions (`approvals`, `cases`, `case_comments`, `audit_events`)

| Field | Level | Notes |
| --- | --- | --- |
| `approvals.approver_id`, `decision`, `amount` | C4 | Immutable finance decision |
| `approvals.reason` | C3 | Free text; unredacted |
| `approvals.signature`, `attestation_hash`, `signer_key_id` | C4 | Tamper evidence |
| `case_comments.body` | C3 | Free text; unredacted |
| `audit_events.old_value`, `new_value` | C3/C4 | Before/after JSON; may include amounts |
| `audit_events.request_id`, `actor_id`, `action` | C2 | Traceability |

### Cryptographic material (`user_signing_keys`, `user_public_keys`, `job_runs`)

| Field | Level | Notes |
| --- | --- | --- |
| `user_signing_keys.encrypted_private_key` | C5 | Fernet-encrypted ECDSA-P256; server-side custody |
| `user_signing_keys.public_key_pem` | C2 | Verification only |
| `user_public_keys.spki_b64` | C2 | Browser-registered public key |
| `job_runs.payload`, `result` | C3 | Scoped identifiers and job outcome |

Signing keys are encrypted with a key derived from `SIGNING_KEY_SECRET`, which
must be distinct from `SECRET_KEY` in production. Possession of the database plus
that secret allows signature forgery for affected users: treat it as C5 and keep it
in a managed secret store. This is server-side custody, not user-held
non-repudiation.

## Emitted data

| Output | Contains | Level |
| --- | --- | --- |
| UI (dashboard, review, outcomes) | Aggregates, amounts, evidence links, free text | C2�?"C4, tenant-scoped |
| `GET /reconciliation/runs/{id}/outcomes` | Frozen sources, formula steps, approver, hashes | C4 |
| Outcomes CSV / JSON report | Line amounts, variance flag, currency, run ID, input hash | C4 |
| Approved-cost export CSV | Approved lines only, integer minor units, provenance | C4 |
| Ingestion downloads | Original bytes (source), normalised rows, validation errors | C3/C4 |
| `GET /audit` | Actor, action, entity, before/after values, request ID | C3/C4 |
| Application logs | Request ID, method, path, status, duration. No bodies, no file content, no credentials | C2 |
| `/metrics` | In-process route counters only | C1/C2, unauthenticated |

No output includes password hashes, encrypted private keys, or session tokens.

## Not collected

No bank account or payment instructions, tax identifiers, payroll data, worker
identity beyond a work reference, GPS or mine telemetry, device fingerprints,
third-party analytics, or document content beyond the uploaded CSV/XLSX. No ERP,
payment, Anaplan or telemetry integration is connected.

## Open items before customer data

- No configurable retention period; purge is manual and per batch.
- No automatic erasure request workflow, and audit records are intentionally not deletable.
- Free-text fields have no redaction or PII guidance at entry.
- `SECRET_KEY` also protects sessions; `SIGNING_KEY_SECRET` must be provisioned and rotated separately.
- No database-level row security; tenant separation is enforced by application scope checks.
