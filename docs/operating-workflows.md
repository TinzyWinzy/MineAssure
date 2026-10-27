# Record management, file ingestion and outcomes

Updated 26 October 2026. The running application is http://localhost:5173; Docker is not required.

## Create, read, update and delete

Use **Details & edit** on Contractors, Contracts, Evidence or Invoices. The detail panel shows linked records, source files and assessment history; association buttons open the related record. Invoice review also has **Edit / associations**.

- Tenant administrators create/rename/delete unused suppliers.
- Contract preparers or administrators create and edit draft contract terms, including supplier association, dates, work code, hourly rate and per-line cap. Approved terms require a new version. Draft-only contracts without linked records can be deleted.
- Operations verifiers create, edit and delete imported, unattested work. Attested or allocated sources remain historical records. The uploader and any editor cannot attest that work themselves.
- AP analysts or administrators create and edit unassessed invoices, change their contract association, and add/edit/remove lines. Amounts are recalculated on the server. Unassessed invoices can be deleted; invoices with assessment history or pending processing are protected.

Edits/deletes require the displayed revision to match the server revision. Deletions require an explicit confirmation in the panel and retain an audit event. Linked suppliers/contracts cannot be removed while referenced. These controls preserve the evidence and approved financial history.

## Process input files

Use **Files** in navigation, or expand **Import CSV / XLSX with validation and outputs** under Evidence or Invoices.

1. Select whether the input contains invoices or operational evidence, and associate it with a contract.
2. Download the matching CSV template if needed. Both templates share an example work reference so their associations are explicit. Use new references for another invoice/work occurrence.
3. Upload UTF-8 CSV or XLSX. XLSX uses the first worksheet; formulas, macros and external workbook links are rejected. Limits are 2 MiB and 500 data rows.
4. Inspect the source preview and map each required field to a source column. Exact matching headers are mapped/validated automatically. Validation does not create business records.
5. Resolve any row/field errors before committing. The whole batch is rejected if any row is invalid; no partial records are accepted.
6. Click **Import … validated rows**. Invoice rows group by supplier invoice number; work rows become unattested records. Created-record buttons open their details/review. Repeating upload/commit returns the existing batch rather than duplicating records.
7. Download the original bytes, processed rows and validation output from the results panel. File history retains status, checksum, associated contract and created records.

Imports preserve original bytes/hash and lineage from invoice/work record to file. Processed rows are canonical data, not payment authority. Files are kept in PostgreSQL for the bounded local workflow; there is no claim of production document quarantine/private object storage or large asynchronous ingestion.

## Associate evidence and calculate outcomes

Choose the same contract for invoice and work inputs. Work reference, code, service date and hour unit must match. A different operations verifier attests imported work under Evidence. An AP analyst then opens the invoice and runs reconciliation through the worker.

**Mathematical outcomes & linked sources** shows the invoice, contract, supplier and evidence associations, frozen rate version, independent verifier, source file, formula steps and decision provenance.

For the paired templates, with an approved USD 240/hour contract:

- Invoiced: 160 hours × USD 250 = USD 40,000.
- Supported: 145 verified hours × USD 240 = USD 34,800.
- Quantified variance: USD 40,000 − USD 34,800 = USD 5,200, counted once.
- Missing/ambiguous evidence or ineligible terms remain unverified; the variance is labelled undetermined.
- Finance approval is a distinct human decision and is a subset of supported costs.

Download **outcomes CSV** for line amounts and **full report** for formulas, frozen input references, hashes and review details. Existing approved-cost export contains only approved lines and remains separately available. Outcome reports do not imply approval or payment.

## API boundaries

- `GET /records/{kind}/{id}` exposes associations and edit/delete policy; `PUT /{kind}/{id}` edits allowed drafts using `expected_revision`.
- `DELETE /{kind}/{id}` and `/records/{kind}/{id}` delete eligible unused records with org/site/revision query parameters.
- `/ingestion/{kind}/stage`, `/{id}/validate`, `/{id}/commit` implement staged file processing. `/{id}/download/source`, `/normalized`, `/errors` return outputs.
- `/reconciliation/runs/{id}/outcomes` and `/report?format=csv|json` expose calculated outcomes and frozen provenance.

Every business endpoint enforces current identity, tenant, site and role on the server. OpenAPI contains exact schemas.
