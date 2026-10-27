# Synthetic pilot UAT checklist

Record tester, timestamp, application revision, database migration head and screenshot/export evidence for each action. Unchecked items are not verified.

- [ ] A new developer starts from one documented command; API readiness and UI become available.
- [ ] Distinct AP, verifier, contract approver and finance personas authenticate; organization/site selection is enforced.
- [ ] A preparer creates a draft hourly contract; another authorized contract approver approves it; self-approval fails.
- [ ] Evidence CSV import shows precise invalid-row messages and preserves source hash. Unattested evidence cannot support an invoice.
- [ ] Attest the 145-hour work record; import/reconcile 160 hours at $250 against $240. Inspect $40,000 invoiced, $34,800 supported and $5,200 once.
- [ ] Reconcile a 10-hour invoice without evidence: $2,400 unverified, no approved amount, no claim of proven overcharge.
- [ ] Bill the same work reference on another invoice; allocation conflict prevents double support.
- [ ] Revise rates effective 15 October; earlier/later service dates use their approved rates while historical results remain unchanged.
- [ ] A draft variation never authorizes extra payable amount.
- [ ] Cross-organization/site requests, wrong-role actions, self-approval and stale-review approval fail.
- [ ] Investigate an exception and record a comment/reason with server-derived actor and timestamp.
- [ ] Finance approves a partial eligible amount. Export includes only approved lines; repeat creation/download preserves rows and hash.
- [ ] Dashboard totals drill to current lines and do not count historical reconciliations twice.
- [ ] Audit view shows source, actor, timestamp and decision provenance.
- [ ] Narrow/mobile and keyboard-only navigation works; error/loading/empty states are understandable.
- [ ] Restore rehearsal succeeds; recovery timings and limitations are recorded.

Real customer UAT, source-document trust, authorization thresholds, privacy and hosting approval remain separate from this synthetic exercise.
