# MineAssure Engineering Review v0.1
Date: 2026-10-25 | Owner: Nexus Agronomics | Status: Internal technical assessment

## Source material reviewed
- MineAssure_PRD_v0.1.docx
- MineAssure_SAD_v0.1.docx
- proof_to_pay_v0_1/app/main.py, test_engine.py, and project structure
- Ran `pytest -q`: 4 passed; 10 FastAPI lifecycle deprecation warnings.

## Verdict
Proof of concept demonstrates contract, work-record and invoice creation, rule-based reconciliation, a review action and dashboard. It does not meet minimum pilot security or financial correctness controls. Do not use for real payable approvals or unattended financial reconciliation.

## Findings
### Critical
C-01 Authentication and review identity: One shared default API key, fixed tenant, caller-specified reviewer string; anyone holding key can submit approval as another reviewer. Implement OIDC/SSO or securely verified user auth, role/site membership, derived identity, authorization, SoD, approval limit enforcement, MFA for privileged users.
C-02 Financial semantics: Missing/multiple evidence and out-of-contract dates cause supported=0 and exposure=billed; this may be misconstrued as proven overcharge. Represent `undetermined`, `unverified_amount`, `quantified_variance`, `approved_amount` separately. No automatic approval for unverified.
C-03 Reuse of evidence: Same work record may be fully utilized by two different invoice references. Introduce allocation reservation/consumption across invoice lines, with transaction/locking and remaining balances. Test concurrent reconciliation and approvals.
C-04 Mutable source of truth: Contract version is an integer in a mutable row, evidence has no verification lifecycle, and reconciliation run only stores version number rather than frozen input content or hashes. Build approved effective-dated contract versions, evidence attestation, immutable snapshots and deterministic replay.
C-05 Workflow integrity: Review endpoint accepts free-text reviewer; no finance approver role, approval thresholds, dual control, optimistic concurrency or audit events; older reconciliations can remain current after later runs. Build transactional state machines, immutable decisions, approvals per eligible lines and automatic stale-run blocking.

### High
H-01 Fixed tenant with no site model and no isolation tests.
H-02 No file upload, mapping, staging, quarantine or CSV/XLSX ingestion.
H-03 Duplicate checks cover reference within same contract and repeated work reference within single invoice; do not cover supplier-wide or cross-invoice fuzzy duplicates.
H-04 No approved export batches, audit event store, download authorization or operational telemetry.
H-05 `Base.metadata.create_all()` at startup instead of migrations; SQLite demo only.
H-06 No currency or tax policy beyond hardcoded USD, no contract model support for shifts, standby, minimums and rate tiers.
H-07 Rules not registered/configurable/versioned in persistence; R005 is used for ambiguous duplicate matching, not actual evidence conflict semantics.
H-08 No health/readiness separation, backups, secret management, retention policy, object storage, signed URLs or vulnerability management.
H-09 Import and reconciliation API routes are synchronous and lack idempotency or batch job lifecycle.
H-10 Test count 4, no tenant/role/SoD, concurrency, exports, property tests, failure modes or performance evidence.

## Clarifications to PRD/SAD before build
- Distinguish potential calculated excess from unverified amount, confirmed adjustment, recovered cash and approved actuals.
- Require explicit price/rate precedence and contract snapshot as-of service date and approval date; prohibit retroactive silent changes.
- Define evidence allocation semantics and concurrency across invoices as P0.
- Define amount arithmetic, taxable basis, rounding at line and document, currency and unit conversion; first pilot supports only USD and one hourly hire pricing type.
- State exactly how partial approvals, appeals and superseding reconciliations work.
- Define scope of access/retention/partner sharing and hosting/data protection for deployment jurisdiction before using client data.
- Normalize naming of REST API to `/api/v1` and document machine-readable error envelopes.
- Add test traceability matrices for all P0 requirements and a staging production-readiness checklist.

## Acceptance gates
G0: Design ADRs, threat model, traceability and golden test fixtures approved.
G1: Auth, migrations, tenant/site isolation, immutable contracts and evidence verified in integration tests.
G2: Deterministic financial engine, allocation ledger, concurrent-safe postings and exception semantics verified by golden/property tests.
G3: Case review, SoD, dual controls, audit proofs and financial export reconciliation pass.
G4: Demonstrable UI, controlled imports, resilience, backups/restore, deploy pipeline and UAT; customer data excluded before written authorization.

## Recommended initial pilot
One mine site, one hourly equipment-hire contract model, USD, independently attested shift records, CSV/XLSX invoices and evidence, 3-5 synthetic anomalies, read-only finance export. Keep Anaplan integration as separately authorized phase 2.
