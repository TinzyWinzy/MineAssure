# MineAssure PRD — source transcription

Source: `MineAssure_PRD_v0.1.docx`. Extracted from the original document paragraphs; table and visual layout is not preserved. The master build prompt and engineering review take precedence where they conflict.

MineAssure — Product Requirements Document

PRD v0.1 | Proof-to-Pay Intelligence for Mining Contractor Costs

NEXUS AGRONOMICS  |  MineAssure  |  v0.1  |  25 October 2026

Status: Draft for internal review and partner discovery. All sample values and commercial assumptions are illustrative.

1. Executive summary

MineAssure is a mining contractor cost-assurance module that evaluates invoice lines against effective contractual terms and independently supported operational records. It creates traceable exceptions and supports human decisions before payable data is exported to downstream finance systems. It is not an ERP, payment processor, safety platform, or autonomous fraud adjudicator.

Primary value proposition: expose potential invoice discrepancies earlier, reduce manual reconciliation effort, and improve the quality of contractor-cost actuals used in financial planning.

2. Problem, customer and outcomes

Mining operations often store contracts, shift logs, equipment hours, weighbridge tickets and contractor invoices in separate systems or spreadsheets. Finance teams may struggle to reproduce why a charge is payable. Disputes can remain unresolved without supporting evidence or a durable audit history.

User / buyer

Need / decision

Mine finance controller / CFO

Prioritise invoice review and understand disputed or unsupported contractor costs.

Contract administrator

Apply correct contract revision, rate schedule and variation approval.

Site operations verifier

Confirm quantity and quality of evidence for delivered work.

AP reviewer / approver

Approve, partially approve, dispute or request documents under delegated limits.

FP&A / modelling partner

Consume reviewed and approved cost actuals with source references.

Success is measured by precision and defensibility, not the volume of exceptions alone.

3. Scope boundaries

In scope — pilot

One mine site and one contractor-workflow family (recommend time-based earthmoving/equipment hire).

Contract register, revisions, validity periods, schedule of rates and approved variations.

CSV/XLSX import plus manual entry for invoices and independently captured operational records.

Line-level reconciliation, explainable discrepancy rules and evidence completeness evaluation.

Case management with assigned reviewer, comments, approval decisions and immutable audit history.

Dashboard, downloadable review pack and approved-cost CSV export.

Organisation/site-scoped permissions; realistic synthetic demo data; operational monitoring and backups.

Explicitly out of scope — v0.1

Automated payments, bank integration and procurement authorisation.

Production Anaplan, SAP or other ERP write-back; connectors are later phase and individually approved.

Automatic accusations of fraud or automatic payment rejection.

Generic extraction of all contract clauses by AI without user confirmation.

Multi-currency tax, complex escalation, commodity-based pricing and advanced equipment telemetry unless selected for pilot.

4. End-to-end user journeys

Journey

User action

Expected state

Contract setup

Create contractor, contract and effective dated rate lines; attach signed terms.

Active, versioned contract after dual review.

Evidence intake

Upload verified daily hours/shift sheets with identity, source and date.

Validated evidence with import errors isolated.

Invoice intake

Import invoice and mapped line items including service periods.

Draft invoice with duplicate fingerprint.

Reconcile

Run rules against relevant contract version and operational evidence.

Reproducible run, evidence links and exceptions.

Resolve

Assign exception, request evidence, record decision and reason.

Open → investigating → resolved / disputed.

Approve / export

Approve supported lines per role/limit; export approved dataset.

Export batch with approver, timestamp and ledger mapping.

5. Functional requirements

ID / priority

Requirement

Acceptance condition

FR-01 P0

Tenant/site segregation and role-based access

User cannot query another tenant or unassigned site through UI or API.

FR-02 P0

Versioned contracts/rates and variations

Rate applied is that effective for the service date, including approved variations.

FR-03 P0

CSV/XLSX intake, mapping and validation

Rejected rows report field/row reason; accepted input retained with checksum.

FR-04 P0

Invoice identity and duplicate review

Identical invoice number per supplier flagged; near-duplicate across dates/lines flagged separately.

FR-05 P0

Operational evidence register

Evidence records have source, verification status, time range and immutable reference.

FR-06 P0

Explainable reconciliation

Output includes invoice amount, evidence-supported amount, difference and rule version per line.

FR-07 P0

Exception review and case state

Every resolution has actor, reason, evidence, timestamp and approval authority.

FR-08 P0

Human payment readiness review

No flagged amount becomes approved automatically; unresolved lines excluded from approved export.

FR-09 P0

Traceable approved-cost exports

Export carries IDs, amounts, currency, period and immutable export batch ID.

FR-10 P1

Dashboard and cost variance trends

Filters reconcile to underlying invoice line totals for selected period/site.

FR-11 P1

Document previews and evidence bundles

Reviewer can retrieve exact source records used in reconciliation.

FR-12 P2

Integration-ready adapters

Documented versioned API and mapping strategy support future ERP/Anaplan connectors.

6. Reconciliation rules and financial semantics

Use decimal arithmetic and explicit currency/rounding policies. Calculate quantities and rates at the invoice-line level. The discrepancy amount is a potential unsupported or over-contract amount, not a confirmed loss. Never silently clamp or combine multiple rule findings into an inflated total. Show a non-double-counted exposure by comparing invoiced versus supported payable amount under the selected contract model.

Rule

Trigger

Decision support

R001 Rate

Invoiced rate exceeds effective approved rate.

Show rate source, date, difference.

R002 Quantity

Invoiced units exceed verified eligible units.

Show evidence records and tolerances.

R003 Duplicate

Exact invoice or materially similar line fingerprints.

Flag candidate, do not auto-reject.

R004 Contract period

Service outside active contract/variation interval.

Require authorised coverage or hold.

R005 Work support

No completed/verified evidence or explicit conflict.

Mark unverified; request documents.

R006 Variation

Variation not approved for affected service date.

Exclude unauthorised adjustment.

R007 Missing documents

Required evidence absent or invalid.

Review hold; retain invoice.

R008 Contract limits

Contract quantity/cap/allowance exceeded.

Calculate threshold overage and trace cap.

Example: 160 hours × $250 invoiced = $40,000; 145 eligible hours × $240 contracted = $34,800; indicative difference = $5,200. This simplified model assumes no minimums, standby, escalation, VAT or approved variations.

7. Roles and approval controls

Role

Rights

Tenant administrator

User/site assignment and configuration; no unilateral finance approval.

Contract manager

Maintain draft rates and variation records; separate approval needed.

Operations verifier

Upload and attest operational records; cannot approve own invoice.

AP analyst

Import invoices, run review and propose resolutions.

Finance approver

Approve/return/dispute within configured monetary delegation.

Auditor / partner viewer

Read-only access scoped to assigned site and approved data.

Enforce separation of duties where feasible: source upload, contract approval and invoice approval should not be performed by the same person for material transactions. Configure monetary thresholds with an escalation route.

8. Data inputs and output contracts

Object

Minimum fields

Contract

tenant, site, contractor, contract ID, effective dates, version, currency, pricing model, status

Rate line

work code, unit, rate decimal, effective interval, tolerance, schedule reference

Operational record

source ID, work code, contractor, site, date/shift, eligible quantity, unit, verifier, attachments

Invoice line

supplier invoice ID, service period, work code, quantity, rate, currency, tax mode

Exception

rule ID/version, record linkage, claimed amount, supported amount, reason, status, owner

Approval/export

decision, approved amount, justification, delegated authority, export ID and timestamp

9. Non-functional requirements and safeguards

Dimension

Pilot target / requirement

Performance

Process 1,000 invoice lines within 60 seconds under measured reference dataset; benchmark before commitment.

Availability

Target 99.5% during agreed pilot service hours; planned downtime notified.

Security

HTTPS/TLS, secure credential handling, MFA for privileged users, organisation/site-scoped RBAC.

Privacy

Encrypt sensitive documents at rest; data minimisation, access logs and tenant-scoped retrieval.

Recovery

Daily encrypted backup; initial design targets RPO ≤24 h, RTO ≤8 h, tested before pilot.

Observability

Structured logs, job status, failures, audit alerts and correlation IDs.

Retention

Contractual retention policy by customer; no silent deletion of financial audit records.

Reliability

Idempotent imports/runs and deterministic calculation results on identical snapshots.

10. KPIs, baselines and success criteria

Metric

Definition / pilot acceptance

Review coverage

≥95% of pilot invoice line value can be matched or explicitly classified unverified.

Reproducibility

100% of sampled findings reproduce under frozen data and rule versions.

Precision

Manual financial review validates ≥90% of high-severity flags; measure against labelled pilot sample.

Traceability

100% of approval and dispute decisions have actor, timestamp, source and reason.

Cycle time

Record pre-pilot hours/invoice; target ≥30% reduction on comparable cases, assessed not promised.

Financial result

Report confirmed recovered/avoided cost separately from potential exposure; zero may be valid.

11. Demo, pilot, dependencies and release gates

Wednesday partner discussion: synthetic data, one equipment-hire contract, a sample shift log and three annotated exceptions.

Pilot entry: sponsor, contract template, permitted data access, operational truth source, approval owners, and security assessment signed off.

Release gate 1: source import and rate version tests; gate 2: reconciliation golden cases; gate 3: role isolation and auditor trace; gate 4: user acceptance and restore rehearsal.

8–10 week delivery estimate assumes one site, one pricing model, timely customer data and no custom production connectors.

Proposed commercial range $12,000–$18,000 remains a hypothesis requiring scope and customer validation.

12. Risks, assumptions and open decisions

Risk / question

Mitigation / decision owner

Operational logs are incomplete or manipulated

Track provenance and confidence; flag missing evidence, do not certify unsupported facts.

Contract wording is bespoke

Validate a supported pricing model before onboarding; legal/contract review remains human.

No common work codes

Add controlled mapping table and mapping approval.

Historical data differs from contract revision

Freeze effective-dated contract snapshots and rerun only with explicit versioning.

False positives or disputed discrepancies

Show evidence, tolerance, case discussion and reversal trail.

Who owns MineAssure IP and 163 Solutions commercial role?

Nexus retains product IP absent separate executed agreement; discovery discussion only.

Which actual mining use case and jurisdiction?

Confirm site, currency, tax treatment, contract type and regulatory posture before production.
