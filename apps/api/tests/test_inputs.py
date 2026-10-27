"""Input APIs must preserve financial semantics before reconciliation."""

from decimal import Decimal

from app.models import ContractVersion, InvoiceLine, Membership


def scope(pilot):
    return {"org_id": pilot["org"], "site_id": pilot["site"]}


def test_evidence_requires_independent_attestation(client, db, pilot):
    body = {
        **scope(pilot),
        "contract_id": pilot["contract"].id,
        "work_reference": "NEW-SHIFT",
        "quantity": "10",
        "service_date": "2026-10-10T00:00:00Z",
    }
    created = client.post(
        "/api/v1/evidence", json=body, headers=pilot["headers"]("operations_verifier")
    )
    assert created.status_code == 200, created.text
    record_id = created.json()["id"]
    assert created.json()["status"] == "imported"
    own = client.post(
        f"/api/v1/evidence/{record_id}/attest",
        headers=pilot["headers"]("operations_verifier"),
    )
    assert own.status_code == 403
    db.add(
        Membership(
            user_id=pilot["users"]["finance_approver"],
            org_id=pilot["org"],
            site_id=pilot["site"],
            role="operations_verifier",
        )
    )
    db.flush()
    independent = client.post(
        f"/api/v1/evidence/{record_id}/attest",
        headers=pilot["headers"]("finance_approver"),
    )
    assert independent.status_code == 200, independent.text
    repeat = client.post(
        f"/api/v1/evidence/{record_id}/attest",
        headers=pilot["headers"]("finance_approver"),
    )
    assert repeat.status_code == 409


def test_contract_preparer_cannot_approve_own_version(client, db, pilot):
    body = {
        **scope(pilot),
        "contractor_id": pilot["contract"].contractor_id,
        "title": "Synthetic new contract",
        "effective_from": "2026-01-01T00:00:00Z",
        "rate": "240",
    }
    created = client.post(
        "/api/v1/contracts", json=body, headers=pilot["headers"]("contract_preparer")
    )
    assert created.status_code == 200, created.text
    contract_id = created.json()["id"]
    db.add(
        Membership(
            user_id=pilot["users"]["contract_preparer"],
            org_id=pilot["org"],
            site_id=pilot["site"],
            role="contract_approver",
        )
    )
    db.flush()
    assert (
        client.post(
            f"/api/v1/contracts/{contract_id}/approve",
            headers=pilot["headers"]("contract_preparer"),
        ).status_code
        == 403
    )
    approved = client.post(
        f"/api/v1/contracts/{contract_id}/approve",
        headers=pilot["headers"]("contract_approver"),
    )
    assert approved.status_code == 200, approved.text
    cv = db.query(ContractVersion).filter_by(contract_id=contract_id).one()
    assert cv.status == "approved" and cv.content_hash
    assert (
        client.post(
            f"/api/v1/contracts/{contract_id}/approve",
            headers=pilot["headers"]("contract_approver"),
        ).status_code
        == 409
    )


def test_imported_line_rounds_half_cent_like_engine(client, db, pilot):
    body = {
        **scope(pilot),
        "contract_id": pilot["contract"].id,
        "supplier_invoice_no": pilot["id"]("halfcent"),
        "lines": [
            {
                "quantity": "0.5",
                "unit_price": "0.01",
                "service_date": "2026-10-10T00:00:00Z",
            }
        ],
    }
    created = client.post("/api/v1/invoices", json=body, headers=pilot["headers"]())
    assert created.status_code == 200, created.text
    line = db.query(InvoiceLine).filter_by(invoice_id=created.json()["id"]).one()
    assert line.amount == Decimal("0.01")


def test_duplicate_supplier_reference_is_rejected_without_second_invoice(client, pilot):
    body = {
        **scope(pilot),
        "contract_id": pilot["contract"].id,
        "supplier_invoice_no": pilot["id"]("same-ref"),
        "lines": [
            {
                "quantity": "10",
                "unit_price": "240",
                "service_date": "2026-10-10T00:00:00Z",
            }
        ],
    }
    first = client.post("/api/v1/invoices", json=body, headers=pilot["headers"]())
    assert first.status_code == 200, first.text
    duplicate = client.post("/api/v1/invoices", json=body, headers=pilot["headers"]())
    assert duplicate.status_code == 409, duplicate.text
