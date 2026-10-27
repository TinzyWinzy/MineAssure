# Synthetic demonstration walkthrough

Start using the root README. Inspect `/ready` and sign into the app with a development persona. The seeded site is a demonstration site; these records are not mining operational evidence.

1. Inspect the approved seed contract as an AP analyst or auditor: USD $240/hour, work code `EQ-HIRE`. Use a contract preparer and distinct contract approver when demonstrating the draft-to-approved workflow.
2. As verifier, inspect or import the 145-hour work record (`docs/examples/evidence.csv`) then sign in as verifier2 to attest it independently. The importing verifier cannot attest their own record. Imported but unattested records must not count as supported. Do not re-import seed references without checking existing records.
3. As AP analyst, inspect the seeded invoice or import `docs/examples/invoices.csv` into the seed contract. Import is bounded; inspect any row errors and source checksum.
4. Reconcile the invoice. The native worker must be running; the UI shows queued/processing status and refreshes on completion. Open the line comparison and explain the invoice rate, approved contract rate, verified hours, findings and single variance. Expected: $40,000 invoiced; $34,800 supported; $5,200 quantified variance. Supported remains provisional.
5. Open the missing-evidence invoice: $2,400 unverified; no confirmed overcharge and no approved amount. An evidence request or investigation is the appropriate next action.
6. Demonstrate a second invoice using the same work reference. It must not obtain another allocation of the same 145 hours. Do not present an allocation conflict as proven fraud.
7. Record an investigation/comment as the allowed reviewer. As a distinct finance approver, approve a supported partial amount, for example $30,000 from the $34,800 eligible amount. If the run/version changed, reload and review instead of bypassing the stale rejection.
8. Create the approved-cost export. Check the partial amount, currency, contract/work code, line identifiers, decision and batch provenance. Repeat the same request/download and verify the same artifact/hash, without a duplicate posting.
9. Review the audit trail and dashboard drill-down. Reconciliation totals are based on current runs; older immutable history remains inspectable.

The exact API request and response schemas are exposed in runtime OpenAPI. When a workflow is disabled or unimplemented, record it in the UAT result rather than improvising a claim. Check `implementation-status.md` for what automated and browser verification actually ran.
