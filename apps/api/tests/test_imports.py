"""CSV parsing, staging, limits and all-or-nothing persistence."""

import hashlib
from decimal import Decimal

import pytest

from app.models import ImportBatch, Invoice, InvoiceLine, WorkRecord

EVIDENCE_HEADER = "work_reference,work_code,quantity,service_date,unit\n"
INVOICE_HEADER = "supplier_invoice_no,work_reference,work_code,quantity,service_date,unit,unit_price\n"


def upload(client, pilot, raw, kind="evidence", filename="synthetic.csv", role=None):
    return client.post(
        f"/api/v1/imports/{kind}",
        params={
            "org_id": pilot["org"],
            "site_id": pilot["site"],
            "contract_id": pilot["contract"].id,
        },
        files={"file": (filename, raw, "text/csv")},
        headers=pilot["headers"](
            role or ("operations_verifier" if kind == "evidence" else "ap_analyst")
        ),
    )


def test_evidence_csv_hash_source_idempotency_and_unattested_state(client, db, pilot):
    raw = (
        EVIDENCE_HEADER + "SHIFT-CSV,EQ-HIRE,145,2026-10-10T00:00:00Z,hour\n"
    ).encode()
    response = upload(client, pilot, raw)
    assert response.status_code == 200, response.text
    batch = response.json()
    assert batch["status"] == "imported" and batch["accepted"] == 1
    assert batch["sha256"] == hashlib.sha256(raw).hexdigest()
    persisted = db.get(ImportBatch, batch["id"])
    assert persisted.source_text == raw.decode()
    work = db.query(WorkRecord).filter_by(contract_id=pilot["contract"].id).one()
    assert work.status == "imported" and work.attested_by is None
    retry = upload(client, pilot, raw)
    assert retry.status_code == 200 and retry.json()["id"] == batch["id"]
    assert db.query(WorkRecord).filter_by(contract_id=pilot["contract"].id).count() == 1


def test_invoice_csv_groups_lines_into_one_document(client, db, pilot):
    raw = (
        INVOICE_HEADER
        + "INV-CSV,A,EQ-HIRE,160,2026-10-10T00:00:00Z,hour,250\nINV-CSV,B,EQ-HIRE,10,2026-10-11T00:00:00Z,hour,240\n"
    ).encode()
    response = upload(client, pilot, raw, kind="invoice")
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "imported" and response.json()["accepted"] == 2
    invoice = db.query(Invoice).filter_by(contract_id=pilot["contract"].id).one()
    assert invoice.import_batch_id == response.json()["id"]
    lines = db.query(InvoiceLine).filter_by(invoice_id=invoice.id).all()
    assert len(lines) == 2 and sum((line.amount for line in lines), Decimal(0)) == 42400


@pytest.mark.parametrize("invalid", ["NaN", "-1", "not-a-number"])
def test_mixed_valid_invalid_rows_rejected_atomically_with_precise_errors(
    client, db, pilot, invalid
):
    raw = (
        EVIDENCE_HEADER
        + "GOOD,EQ-HIRE,10,2026-10-10T00:00:00Z,hour\n"
        + f"BAD,EQ-HIRE,{invalid},2026-10-10T00:00:00Z,hour\n"
    ).encode()
    response = upload(client, pilot, raw)
    assert response.status_code == 200, response.text
    batch = response.json()
    assert batch["status"] == "rejected" and batch["accepted"] == 0
    assert any(error["row"] == 3 for error in batch["errors"])
    assert db.query(WorkRecord).filter_by(contract_id=pilot["contract"].id).count() == 0
    assert db.get(ImportBatch, batch["id"]).source_text == raw.decode()


def test_domain_rejection_rolls_back_previously_inserted_valid_row(client, db, pilot):
    raw = (
        EVIDENCE_HEADER
        + "GOOD,EQ-HIRE,10,2026-10-10T00:00:00Z,hour\nBAD,EQ-HIRE,10,2026-10-10T00:00:00Z,metre\n"
    ).encode()
    response = upload(client, pilot, raw)
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "rejected" and response.json()["accepted"] == 0
    assert db.query(WorkRecord).filter_by(contract_id=pilot["contract"].id).count() == 0


@pytest.mark.parametrize(
    "raw,filename,status",
    [
        (b"a" * (256 * 1024 + 1), "big.csv", 413),
        (b"\xff\xfe", "binary.csv", 422),
        (b"a\x00b", "binary.csv", 422),
        (b"payload", "macro.xlsm", 422),
    ],
    ids=["oversized", "non-utf8", "null-byte", "unsupported-extension"],
)
def test_oversized_binary_or_non_csv_uploads_are_rejected(
    client, db, pilot, raw, filename, status
):
    response = upload(client, pilot, raw, filename=filename)
    assert response.status_code == status, response.text
    assert db.query(WorkRecord).filter_by(contract_id=pilot["contract"].id).count() == 0


def test_row_limit_stages_rejection_without_partial_inserts(client, db, pilot):
    raw = EVIDENCE_HEADER + "".join(
        f"SHIFT-{number},EQ-HIRE,1,2026-10-10T00:00:00Z,hour\n" for number in range(501)
    )
    response = upload(client, pilot, raw.encode())
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "rejected" and response.json()["accepted"] == 0
    assert any("500" in error["message"] for error in response.json()["errors"])
    assert db.query(WorkRecord).filter_by(contract_id=pilot["contract"].id).count() == 0


@pytest.mark.parametrize(
    "raw",
    [
        b"wrong,headers\n1,2\n",
        EVIDENCE_HEADER.encode(),
        (EVIDENCE_HEADER + '"unterminated').encode(),
        (
            EVIDENCE_HEADER + "A,EQ-HIRE,1,2026-10-10T00:00:00Z,hour,unexpected\n"
        ).encode(),
    ],
)
def test_malformed_missing_empty_or_extra_columns_are_staged_rejections(
    client, pilot, raw
):
    response = upload(client, pilot, raw)
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "rejected" and response.json()["errors"]


def test_wrong_role_and_foreign_tenant_uploads_denied(client, pilot):
    raw = (EVIDENCE_HEADER + "SHIFT,EQ-HIRE,1,2026-10-10T00:00:00Z,hour\n").encode()
    assert upload(client, pilot, raw, role="auditor").status_code == 403
    assert upload(client, pilot, raw, role="outsider").status_code == 403
