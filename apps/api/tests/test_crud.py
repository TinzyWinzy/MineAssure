from decimal import Decimal

from test_persistence import run_invoice

from app.models import (
    AuditEvent,
    Contract,
    Contractor,
    Invoice,
    InvoiceLine,
    Membership,
    WorkRecord,
)


def params(pilot):
    return {"org_id": pilot["org"], "site_id": pilot["site"]}


def invoice_body(pilot, reference="EDITED", quantity="12", price="241"):
    return {
        **params(pilot),
        "contract_id": pilot["contract"].id,
        "supplier_invoice_no": reference,
        "lines": [
            {
                "quantity": quantity,
                "unit_price": price,
                "service_date": "2026-10-10",
                "work_reference": "EDITED-SHIFT",
            }
        ],
    }


def test_invoice_read_edit_associate_and_delete_unused_draft(client, db, pilot):
    invoice, old_line = pilot["invoice"]()
    old_line_id = old_line.id
    url = f"/api/v1/records/invoices/{invoice.id}"
    detail = client.get(url, params=params(pilot), headers=pilot["headers"]())
    assert detail.status_code == 200
    assert detail.json()["can_edit"]
    assert detail.json()["associations"]["contract"]["id"] == pilot["contract"].id
    changed = client.put(
        f"/api/v1/invoices/{invoice.id}",
        params={"expected_revision": 1},
        json=invoice_body(pilot),
        headers=pilot["headers"](),
    )
    assert changed.status_code == 200, changed.text
    db.expire_all()
    lines = db.query(InvoiceLine).filter_by(invoice_id=invoice.id).all()
    assert len(lines) == 1 and lines[0].amount == Decimal(2892)
    assert lines[0].id != old_line_id
    assert db.get(Invoice, invoice.id).created_by == pilot["users"]["ap_analyst"]
    stale = client.put(
        f"/api/v1/invoices/{invoice.id}",
        params={"expected_revision": 1},
        json=invoice_body(pilot),
        headers=pilot["headers"](),
    )
    assert stale.status_code == 409
    removed = client.delete(
        url,
        params={**params(pilot), "expected_revision": 2},
        headers=pilot["headers"](),
    )
    assert removed.status_code == 200, removed.text
    assert (
        client.get(url, params=params(pilot), headers=pilot["headers"]()).status_code
        == 404
    )
    assert (
        db.query(AuditEvent)
        .filter_by(entity_id=invoice.id, action="invoice.updated")
        .count()
        == 1
    )


def test_processed_invoice_cannot_be_edited_deleted_or_reassociated(client, pilot):
    invoice, _ = pilot["invoice"]()
    pilot["evidence"]()
    assert run_invoice(client, pilot, invoice).status_code == 200
    detail = client.get(
        f"/api/v1/records/invoices/{invoice.id}",
        params=params(pilot),
        headers=pilot["headers"](),
    ).json()
    assert not detail["can_edit"] and detail["associations"]["runs"]
    assert (
        client.put(
            f"/api/v1/invoices/{invoice.id}",
            params={"expected_revision": 1},
            json=invoice_body(pilot),
            headers=pilot["headers"](),
        ).status_code
        == 409
    )
    assert (
        client.delete(
            f"/api/v1/records/invoices/{invoice.id}",
            params={**params(pilot), "expected_revision": 1},
            headers=pilot["headers"](),
        ).status_code
        == 409
    )


def test_evidence_crud_and_immutable_attested_source(client, db, pilot):
    work = pilot["evidence"](status="imported")
    body = {
        **params(pilot),
        "contract_id": pilot["contract"].id,
        "work_reference": "CORRECTED",
        "quantity": "144",
        "service_date": "2026-10-10",
    }
    changed = client.put(
        f"/api/v1/evidence/{work.id}",
        params={"expected_revision": 1},
        json=body,
        headers=pilot["headers"]("operations_verifier"),
    )
    assert changed.status_code == 200, changed.text
    assert db.get(WorkRecord, work.id).quantity == 144
    assert (
        client.post(
            f"/api/v1/evidence/{work.id}/attest",
            headers=pilot["headers"]("operations_verifier"),
        ).status_code
        == 403
    )
    removed = client.delete(
        f"/api/v1/records/evidence/{work.id}",
        params={**params(pilot), "expected_revision": 2},
        headers=pilot["headers"]("operations_verifier"),
    )
    assert removed.status_code == 200, removed.text
    attested = pilot["evidence"]("immutable")
    assert (
        client.put(
            f"/api/v1/evidence/{attested.id}",
            params={"expected_revision": 1},
            json=body,
            headers=pilot["headers"]("operations_verifier"),
        ).status_code
        == 409
    )


def test_draft_contract_crud_and_supplier_reference_protection(client, db, pilot):
    body = {
        **params(pilot),
        "contractor_id": pilot["contract"].contractor_id,
        "title": "Editable draft",
        "effective_from": "2026-01-01",
        "rate": "240",
    }
    created = client.post(
        "/api/v1/contracts", json=body, headers=pilot["headers"]("contract_preparer")
    ).json()
    body.update(title="Edited draft", rate="255")
    changed = client.put(
        f"/api/v1/contracts/{created['id']}",
        params={"expected_revision": 1},
        json=body,
        headers=pilot["headers"]("contract_preparer"),
    )
    assert changed.status_code == 200, changed.text
    removed = client.delete(
        f"/api/v1/records/contracts/{created['id']}",
        params={**params(pilot), "expected_revision": 2},
        headers=pilot["headers"]("contract_preparer"),
    )
    assert removed.status_code == 200 and not db.get(Contract, created["id"])
    db.add(
        Membership(
            user_id=pilot["users"]["auditor"],
            org_id=pilot["org"],
            site_id=None,
            role="tenant_admin",
        )
    )
    db.flush()
    supplier = client.post(
        "/api/v1/contractors",
        json={**params(pilot), "name": "Temporary"},
        headers=pilot["headers"]("auditor"),
    ).json()
    changed = client.put(
        f"/api/v1/contractors/{supplier['id']}",
        params={"expected_revision": 1},
        json={**params(pilot), "name": "Renamed"},
        headers=pilot["headers"]("auditor"),
    )
    assert changed.status_code == 200
    assert (
        client.delete(
            f"/api/v1/records/contractors/{supplier['id']}",
            params={**params(pilot), "expected_revision": 2},
            headers=pilot["headers"]("auditor"),
        ).status_code
        == 200
    )
    assert (
        client.delete(
            f"/api/v1/records/contractors/{pilot['contract'].contractor_id}",
            params={**params(pilot), "expected_revision": 1},
            headers=pilot["headers"]("auditor"),
        ).status_code
        == 409
    )
    assert db.get(Contractor, pilot["contract"].contractor_id)


def test_crud_denies_wrong_role_site_and_tenant(client, pilot):
    invoice, _ = pilot["invoice"]()
    for role in ("auditor", "outsider"):
        assert (
            client.put(
                f"/api/v1/invoices/{invoice.id}",
                params={"expected_revision": 1},
                json=invoice_body(pilot),
                headers=pilot["headers"](role),
            ).status_code
            == 403
        )
    assert (
        client.get(
            f"/api/v1/records/invoices/{invoice.id}",
            params={"org_id": pilot["org"], "site_id": pilot["other_site"]},
            headers=pilot["headers"](),
        ).status_code
        == 403
    )


def test_invoice_editor_cannot_financially_approve_even_with_finance_role(
    client, db, pilot
):
    from test_persistence import approve

    invoice, line = pilot["invoice"]()
    pilot["evidence"]()
    uid = pilot["users"]["finance_approver"]
    db.add(
        Membership(
            user_id=uid, org_id=pilot["org"], site_id=pilot["site"], role="ap_analyst"
        )
    )
    db.flush()
    body = invoice_body(pilot, quantity="145", price="240")
    body["lines"][0]["work_reference"] = "SHIFT-A"
    changed = client.put(
        f"/api/v1/invoices/{invoice.id}",
        params={"expected_revision": 1},
        json=body,
        headers=pilot["headers"]("finance_approver"),
    )
    assert changed.status_code == 200
    db.expire_all()
    line = db.query(InvoiceLine).filter_by(invoice_id=invoice.id).one()
    run = run_invoice(client, pilot, invoice).json()
    assert approve(client, pilot, run, line).status_code == 403
