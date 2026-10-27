import csv
import hashlib
import io
from decimal import Decimal

import pytest
from openpyxl import Workbook
from test_persistence import run_invoice

from app.models import Invoice, WorkRecord


def stage(client, pilot, raw, kind="evidence", filename="work.csv", role=None):
    return client.post(
        f"/api/v1/ingestion/{kind}/stage",
        params={
            "org_id": pilot["org"],
            "site_id": pilot["site"],
            "contract_id": pilot["contract"].id,
        },
        files={"file": (filename, raw)},
        headers=pilot["headers"](
            role or ("ap_analyst" if kind == "invoice" else "operations_verifier")
        ),
    )


def workbook(rows):
    book = Workbook()
    for row in rows:
        book.active.append(row)
    output = io.BytesIO()
    book.save(output)
    book.close()
    return output.getvalue()


def test_xlsx_mapping_preview_commit_links_original_and_processed_outputs(
    client, db, pilot
):
    raw = workbook(
        [
            ["Shift", "Code", "Hours", "Date", "Unit"],
            ["XLSX-A", "EQ-HIRE", 145, "2026-10-10", "hour"],
        ]
    )
    response = stage(client, pilot, raw, filename="shifts.xlsx")
    assert response.status_code == 200, response.text
    batch = response.json()
    assert batch["status"] == "staged" and batch["preview"][0][2] == "145"
    assert db.query(WorkRecord).filter_by(import_batch_id=batch["id"]).count() == 0
    response = client.post(
        f"/api/v1/ingestion/{batch['id']}/validate",
        json={
            "mapping": {
                "work_reference": "Shift",
                "work_code": "Code",
                "quantity": "Hours",
                "service_date": "Date",
                "unit": "Unit",
            }
        },
        headers=pilot["headers"]("operations_verifier"),
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "ready"
    committed = client.post(
        f"/api/v1/ingestion/{batch['id']}/commit",
        json={},
        headers=pilot["headers"]("operations_verifier"),
    )
    assert committed.status_code == 200, committed.text
    assert committed.json()["accepted"] == 1
    work = db.query(WorkRecord).filter_by(import_batch_id=batch["id"]).one()
    assert work.quantity == 145 and work.status == "imported"
    source = client.get(
        f"/api/v1/ingestion/{batch['id']}/download/source",
        headers=pilot["headers"]("auditor"),
    )
    assert source.content == raw
    assert hashlib.sha256(source.content).hexdigest() == batch["sha256"]
    normalized = client.get(
        f"/api/v1/ingestion/{batch['id']}/download/normalized",
        headers=pilot["headers"]("auditor"),
    )
    assert (
        next(iter(csv.DictReader(io.StringIO(normalized.content.decode("utf-8-sig")))))[
            "work_reference"
        ]
        == "XLSX-A"
    )
    repeated = client.post(
        f"/api/v1/ingestion/{batch['id']}/commit",
        json={},
        headers=pilot["headers"]("operations_verifier"),
    )
    assert repeated.json()["created_records"] == committed.json()["created_records"]
    assert stage(client, pilot, raw, filename="shifts.xlsx").json()["id"] == batch["id"]


def test_invalid_file_rows_have_precise_output_and_cannot_partially_import(
    client, db, pilot
):
    raw = b"work_reference,work_code,quantity,service_date,unit\nGOOD,EQ-HIRE,10,2026-10-10,hour\nBAD,EQ-HIRE,-1,2026-10-10,hour\n"
    response = stage(client, pilot, raw)
    assert response.status_code == 200, response.text
    batch = response.json()
    assert batch["status"] == "rejected"
    assert any(e["row"] == 3 and e["field"] == "quantity" for e in batch["errors"])
    assert (
        client.post(
            f"/api/v1/ingestion/{batch['id']}/commit",
            json={},
            headers=pilot["headers"]("operations_verifier"),
        ).status_code
        == 409
    )
    assert db.query(WorkRecord).filter_by(import_batch_id=batch["id"]).count() == 0
    errors = client.get(
        f"/api/v1/ingestion/{batch['id']}/download/errors", headers=pilot["headers"]()
    ).content.decode("utf-8-sig")
    assert "quantity" in errors and "3," in errors


def test_invoice_csv_ingestion_preserves_associations_and_prevents_duplicate_commit(
    client, db, pilot
):
    raw = b"supplier_invoice_no,work_reference,work_code,quantity,service_date,unit,unit_price\nFILE-INV,A,EQ-HIRE,160,2026-10-10,hour,250\nFILE-INV,B,EQ-HIRE,10,2026-10-11,hour,240\n"
    batch = stage(client, pilot, raw, kind="invoice", filename="invoices.csv").json()
    committed = client.post(
        f"/api/v1/ingestion/{batch['id']}/commit", json={}, headers=pilot["headers"]()
    )
    assert committed.status_code == 200, committed.text
    assert (
        committed.json()["accepted"] == 2
        and len(committed.json()["created_records"]) == 1
    )
    invoice = db.query(Invoice).filter_by(import_batch_id=batch["id"]).one()
    detail = client.get(
        f"/api/v1/records/invoices/{invoice.id}",
        params={"org_id": pilot["org"], "site_id": pilot["site"]},
        headers=pilot["headers"](),
    ).json()
    assert detail["associations"]["import"]["id"] == batch["id"]
    assert detail["item"]["total"] == "42400.000000"
    duplicate = raw.replace(b"250", b"251")
    other = stage(
        client, pilot, duplicate, kind="invoice", filename="another.csv"
    ).json()
    rejected = client.post(
        f"/api/v1/ingestion/{other['id']}/commit", json={}, headers=pilot["headers"]()
    )
    assert rejected.json()["status"] == "rejected"
    assert db.query(Invoice).filter_by(contract_id=pilot["contract"].id).count() == 1


@pytest.mark.parametrize(
    "invalid", ["=SUM(1,2)", '=HYPERLINK("https://example.invalid")']
)
def test_workbook_formula_cells_are_rejected(client, pilot, invalid):
    raw = workbook(
        [
            ["work_reference", "work_code", "quantity", "service_date", "unit"],
            ["UNTRUSTED", "EQ-HIRE", invalid, "2026-10-10", "hour"],
        ]
    )
    response = stage(client, pilot, raw, filename="formula.xlsx")
    assert response.status_code == 422 and "Formula" in response.json()["detail"]


def test_file_download_and_ingestion_are_role_and_tenant_scoped(client, pilot):
    raw = b"work_reference,work_code,quantity,service_date,unit\nSAFE,EQ-HIRE,10,2026-10-10,hour\n"
    assert stage(client, pilot, raw, role="auditor").status_code == 403
    assert stage(client, pilot, raw, role="outsider").status_code == 403
    batch = stage(client, pilot, raw).json()
    for path in (
        f"/api/v1/ingestion/{batch['id']}",
        f"/api/v1/ingestion/{batch['id']}/download/source",
    ):
        assert client.get(path, headers=pilot["headers"]("outsider")).status_code == 403
    assert (
        client.post(
            f"/api/v1/ingestion/{batch['id']}/commit",
            json={},
            headers=pilot["headers"]("auditor"),
        ).status_code
        == 403
    )


def test_math_output_proves_conservation_and_freezes_sources(client, db, pilot):
    invoice, _ = pilot["invoice"]()
    pilot["evidence"]()
    run = run_invoice(client, pilot, invoice).json()
    response = client.get(
        f"/api/v1/reconciliation/runs/{run['id']}/outcomes", headers=pilot["headers"]()
    )
    assert response.status_code == 200, response.text
    report = response.json()
    assert report["totals"] == {
        "invoiced_amount": "40000.00",
        "supported_amount": "34800.00",
        "unverified_amount": "0.00",
        "quantified_variance": "5200.00",
        "approved_amount": "0.00",
    }
    line = report["lines"][0]
    assert line["conservation_valid"] and line["variance_determined"]
    assert Decimal(line["evidence_sources"][0]["quantity"]) == 145
    assert any(
        "145" in step["formula"] and step["value"] == "34800.00"
        for step in line["calculation_steps"]
    )
    csv_report = client.get(
        f"/api/v1/reconciliation/runs/{run['id']}/report?format=csv",
        headers=pilot["headers"]("auditor"),
    )
    assert csv_report.status_code == 200 and "5200" in csv_report.text
    assert (
        client.get(
            f"/api/v1/reconciliation/runs/{run['id']}/report?format=json",
            headers=pilot["headers"]("outsider"),
        ).status_code
        == 403
    )
    pilot["cv"].status = "draft"
    db.flush()
    historical = client.get(
        f"/api/v1/reconciliation/runs/{run['id']}/outcomes", headers=pilot["headers"]()
    ).json()
    assert historical["lines"][0]["contract_source"] == line["contract_source"]


def test_missing_evidence_output_marks_variance_undetermined(client, pilot):
    invoice, _ = pilot["invoice"](hours="10", rate="240", ref="NO-SOURCE")
    run = run_invoice(client, pilot, invoice).json()
    report = client.get(
        f"/api/v1/reconciliation/runs/{run['id']}/outcomes", headers=pilot["headers"]()
    ).json()
    assert report["totals"]["unverified_amount"] == "2400.00"
    assert report["lines"][0]["variance_determined"] is False


def test_blank_source_rows_do_not_shift_validation_error_numbers(client, pilot):
    raw = b"work_reference,work_code,quantity,service_date,unit\n\nBAD,EQ-HIRE,-1,2026-10-10,hour\n"
    response = stage(client, pilot, raw)
    assert response.status_code == 200
    assert response.json()["errors"][0]["row"] == 3
