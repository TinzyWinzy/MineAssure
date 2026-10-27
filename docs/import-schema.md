# Staged CSV / XLSX processing

The Files workspace now supports CSV/XLSX upload → column mapping → preview/validation → atomic import. Limits: 2 MiB, 500 rows; XLSX uses the first worksheet and rejects formulas/macros/external links. Download input templates in the UI, then inspect original/processed/error outputs and linked records. See [operating workflows](operating-workflows.md). Original bytes/hash are retained; evidence remains unattested until independently reviewed.

The older one-step CSV API below remains available with its original limits.

# Bounded CSV import schema

Synthetic pilot endpoint: `POST /api/v1/imports/{kind}` with multipart field `file` and query parameters `org_id`, `site_id`, `contract_id`. Inspect runtime OpenAPI for the accepted `kind` values and exact response shape. Contract and site must be accessible to the caller, belong to the same organization, and use the supported pricing model.

| Input | Required CSV columns |
| --- | --- |
| Operational evidence | `work_reference,work_code,quantity,service_date,unit` |
| Invoice lines | `supplier_invoice_no,work_reference,work_code,quantity,unit_price,service_date,unit` |

Use UTF-8 CSV, ISO-8601 UTC timestamps, positive decimal quantity, nonnegative decimal unit price, unit `hour` and work code `EQ-HIRE` for the seed contract. Pass numbers as strings in JSON workflows to avoid binary floating-point transport issues. The server owns amount calculations. Do not import tax, currency conversion, formulas, minimums or standby into the hourly demo.

The bounded synchronous import accepts at most 500 rows and 256 KiB. Kinds are `evidence` (alias `work`) and `invoice`; `GET /api/v1/imports` reports accepted/error rows. A batch is committed all-or-nothing: invalid rows reject canonical writes, while source text/hash and precise row errors remain available for inspection. Evidence starts unverified until an authorized operations verifier attests it. Invoice import and evidence attestation use distinct roles. Examples are in `docs/examples/`; use unique source references when importing into an already used environment.

XLSX, configurable column mapping, binary document quarantine/scanning, object storage downloads and large asynchronous import are not delivered by this bounded path. A MinIO service profile alone does not implement document handling.
