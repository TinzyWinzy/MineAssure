# Requirements and verification traceability

This matrix links the source PRD IDs to code boundaries and evidence locations. A test file's existence is not a passing result; actual executed commands and results are recorded in `implementation-status.md`.

| Requirement / golden case | Implementation boundary | Evidence / residual gate |
| --- | --- | --- |
| FR-01 / F: tenant/site/RBAC/IDOR | `app/auth.py`, scoped API queries | Backend integration/security suite; database RLS and production identity still required. |
| FR-02 / D,E: effective approved versions | Contract API, `app/engine.py` | Contract revision API/history, stale approval target and version/date/draft tests; unsupported pricing exceptions stay outside pilot. |
| FR-03: ingestion and validation | Staged CSV/XLSX processing, mapping, preview, validation, commit and original/processed/error downloads | API and browser file-workflow tests; malware scanning and durable large-file ingestion remain outstanding. |
| FR-04 / H: invoice/work duplicates | Invoice identity, reconciliation matching | Duplicate/allocation tests; customer fuzzy-match policy and false-positive assessment remain. |
| FR-05: operational support | Work records, attestation and allocations | Unattested/missing evidence tests; independently trusted real sources require customer agreement. |
| FR-06 / A,B,C: explainable reconciliation | Decimal engine, immutable run/results | Golden and allocation tests; actual run/snapshot behavior must be verified by API tests. |
| FR-07: case review | Cases/comments and audit events | Authorized comments/review tests; full dispute/escalation/reversal lifecycle may be partial. |
| FR-08 / F: human approval | Current run, distinct approver, monetary checks | Stale/self/wrong-role/unverified approval tests. |
| FR-09 / G: approved-cost export | Persisted decision and export snapshot | Partial/repeated/export hash tests. |
| FR-10: dashboard | Current run aggregation and scoped detail | UI/API reconciliation checks; no recovery/savings claims. |
| FR-11: document/evidence pack | Source snapshots/hash | Binary previews, private signed downloads and full review bundle remain a release gate. |
| FR-12: integration | Versioned API, approved CSV | External connectors deliberately absent. |
| NFR: resilience/performance/accessibility | Compose, backup script, frontend | 126 PostgreSQL tests, 5 browser finance/admin/mobile/file/CRUD journeys, WCAG A/AA smoke checks, 1,000 persisted lines in 11.8475 s and native 26-table restore; customer SLA and production recovery remain open. |

Durable reconciliation is implemented in app/worker.py with lease/retry/replay/authorization tests and a concurrent SKIP LOCKED claim test. Native start/stop/verify scripts are the active local workflow. See implementation-status.md for executed evidence and remaining master-build requirements. This development verification is not an independent production certification.

CRUD and associations: app/routers/records.py and RecordPanel.tsx provide draft editing/deletion with revision checks, protected historical sources and related-record navigation. Outcome reports expose mathematical formula steps and input/decision provenance in app/routers/outcomes.py and OutcomePanel.tsx.
