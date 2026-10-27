"""Golden pilot and adversarial financial workflow tests on PostgreSQL."""

import csv
import hashlib
import io
from datetime import UTC
from decimal import Decimal

import pytest

from app.models import AuditEvent, EvidenceAllocation, Membership, ReconciliationRun


def run_invoice(client, pilot, invoice, **extra):
    return client.post(
        "/api/v1/reconciliation/runs",
        json={
            "org_id": pilot["org"],
            "site_id": pilot["site"],
            "invoice_id": invoice.id,
            **extra,
        },
        headers=pilot["headers"](),
    )


def approve(client, pilot, run, line, amount="34800", role="finance_approver", **extra):
    return client.post(
        "/api/v1/approvals",
        json={
            "run_id": run["id"],
            "invoice_line_id": line.id,
            "decision": "approved",
            "amount": amount,
            "reason": "Independent financial review of synthetic pilot evidence",
            "run_version": run["version"],
            **extra,
        },
        headers=pilot["headers"](role),
    )


def export(client, pilot, run, **extra):
    return client.post(
        "/api/v1/exports",
        json={
            "org_id": pilot["org"],
            "site_id": pilot["site"],
            "run_id": run["id"],
            **extra,
        },
        headers=pilot["headers"]("finance_approver"),
    )


def test_golden_a_partial_approval_and_idempotent_export(client, db, pilot):
    invoice, line = pilot["invoice"]()
    pilot["evidence"]()
    response = run_invoice(client, pilot, invoice)
    assert response.status_code == 200, response.text
    run = response.json()
    result = run["results"][0]
    assert Decimal(result["invoiced_amount"]) == Decimal(40000)
    assert Decimal(result["supported_amount"]) == Decimal(34800)
    assert Decimal(result["quantified_variance"]) == Decimal(5200)
    assert {"R001", "R002"} <= {finding["rule_code"] for finding in result["findings"]}
    assert Decimal(result["approved_amount"]) == 0
    assert run.get("input_hash") and run.get("input_snapshot")
    approval = approve(client, pilot, run, line, "30000")
    assert approval.status_code == 200, approval.text
    repeated = approve(client, pilot, run, line, "30000")
    assert repeated.status_code in (200, 409), repeated.text
    batch = export(client, pilot, run, idempotency_key=pilot["id"]("export"))
    assert batch.status_code == 200, batch.text
    assert batch.json()["total_minor"] == 3000000
    repeated_batch = export(client, pilot, run, idempotency_key=pilot["id"]("export"))
    assert repeated_batch.status_code == 200, repeated_batch.text
    assert repeated_batch.json()["id"] == batch.json()["id"]
    assert repeated_batch.json()["total_minor"] == 3000000
    download = client.get(
        f"/api/v1/exports/{batch.json()['id']}/download",
        headers=pilot["headers"]("auditor"),
    )
    assert download.status_code == 200, download.text
    assert hashlib.sha256(download.content).hexdigest() == batch.json()["artifact_hash"]
    rows = list(csv.DictReader(io.StringIO(download.text)))
    assert sum(int(row["amount_minor"]) for row in rows) == 3000000
    assert db.query(AuditEvent).filter(AuditEvent.org_id == pilot["org"]).count() >= 3


def test_missing_evidence_is_unverified_and_cannot_be_approved(client, pilot):
    invoice, line = pilot["invoice"](hours="10", rate="240", ref="MISSING")
    response = run_invoice(client, pilot, invoice)
    assert response.status_code == 200, response.text
    run = response.json()
    result = run["results"][0]
    assert Decimal(result["unverified_amount"]) == 2400
    assert Decimal(result["quantified_variance"]) == 0
    assert Decimal(result["supported_amount"]) == 0
    assert approve(client, pilot, run, line, "2400").status_code in (400, 409, 422)
    assert export(client, pilot, run).status_code in (400, 409, 422)


def test_client_cannot_supply_verified_quantity(client, pilot):
    invoice, line = pilot["invoice"]()
    response = run_invoice(
        client,
        pilot,
        invoice,
        lines=[
            {
                "invoice_line_id": line.id,
                "verified_qty": "999999",
                "evidence_work_refs": ["invented"],
            }
        ],
    )
    assert response.status_code == 422


def test_cross_invoice_evidence_reuse_is_blocked(client, db, pilot):
    first, _ = pilot["invoice"]("A", hours="10", rate="240")
    second, second_line = pilot["invoice"]("B", hours="10", rate="240")
    work = pilot["evidence"](hours="10")
    a = run_invoice(client, pilot, first)
    assert a.status_code == 200, a.text
    b = run_invoice(client, pilot, second)
    assert b.status_code == 200, b.text
    result = b.json()["results"][0]
    assert Decimal(result["supported_amount"]) == 0
    assert Decimal(result["unverified_amount"]) == 2400
    assert any(f["rule_code"] in ("R003", "R005") for f in result["findings"])
    active = (
        db.query(EvidenceAllocation)
        .filter(
            EvidenceAllocation.work_record_id == work.id,
            EvidenceAllocation.status.in_(["reserved", "consumed"]),
        )
        .all()
    )
    assert sum((row.quantity for row in active), Decimal(0)) <= 10
    assert approve(client, pilot, b.json(), second_line, "2400").status_code in (
        400,
        409,
        422,
    )


@pytest.mark.parametrize(
    "role", ["auditor", "partner_readonly", "operations_verifier", "finance_approver"]
)
def test_wrong_role_cannot_reconcile(client, pilot, role):
    invoice, _ = pilot["invoice"]()
    response = client.post(
        "/api/v1/reconciliation/runs",
        json={
            "org_id": pilot["org"],
            "site_id": pilot["site"],
            "invoice_id": invoice.id,
        },
        headers=pilot["headers"](role),
    )
    assert response.status_code == 403


def test_run_read_approval_export_deny_other_tenant(client, pilot):
    invoice, line = pilot["invoice"]()
    pilot["evidence"]()
    run = run_invoice(client, pilot, invoice).json()
    headers = pilot["headers"]("outsider")
    assert client.get(
        f"/api/v1/reconciliation/runs/{run['id']}", headers=headers
    ).status_code in (403, 404)
    assert approve(client, pilot, run, line, role="outsider").status_code in (403, 404)
    denied = client.post(
        "/api/v1/exports",
        json={
            "org_id": pilot["foreign_org"],
            "run_id": run["id"],
            "site_id": pilot["site"],
        },
        headers=headers,
    )
    assert denied.status_code in (403, 404)


def test_unassigned_site_read_and_write_denied(client, pilot):
    invoice, _ = pilot["invoice"](at_site=pilot["other_site"])
    assert run_invoice(client, pilot, invoice).status_code in (403, 404)
    response = client.get(
        f"/api/v1/invoices?org_id={pilot['org']}&site_id={pilot['other_site']}",
        headers=pilot["headers"](),
    )
    assert response.status_code in (403, 404)


def test_scoped_role_does_not_borrow_finance_role(client, db, pilot):
    invoice, line = pilot["invoice"]()
    pilot["evidence"]()
    run = run_invoice(client, pilot, invoice).json()
    db.add(
        Membership(
            user_id=pilot["users"]["auditor"],
            org_id=pilot["foreign_org"],
            site_id=None,
            role="finance_approver",
        )
    )
    db.flush()
    assert approve(client, pilot, run, line, role="auditor").status_code == 403


def test_self_approval_is_forbidden_even_with_both_roles(client, db, pilot):
    invoice, line = pilot["invoice"]()
    pilot["evidence"]()
    run = run_invoice(client, pilot, invoice).json()
    db.add(
        Membership(
            user_id=pilot["users"]["ap_analyst"],
            org_id=pilot["org"],
            site_id=pilot["site"],
            role="finance_approver",
        )
    )
    db.flush()
    assert approve(client, pilot, run, line, role="ap_analyst").status_code == 403


def test_stale_run_and_wrong_version_cannot_be_approved(client, db, pilot):
    invoice, line = pilot["invoice"]()
    pilot["evidence"]()
    run = run_invoice(client, pilot, invoice).json()
    assert (
        approve(client, pilot, run, line, run_version=run["version"] + 1).status_code
        == 409
    )
    persisted = db.get(ReconciliationRun, run["id"])
    persisted.is_current = False
    db.flush()
    assert approve(client, pilot, run, line).status_code == 409


@pytest.mark.parametrize(
    "amount", ["-1", "0", "34800.01", "40000", "NaN", "Infinity", "0.001"]
)
def test_invalid_or_unsupported_approval_amount_rejected(client, pilot, amount):
    invoice, line = pilot["invoice"]()
    pilot["evidence"]()
    run = run_invoice(client, pilot, invoice).json()
    assert approve(client, pilot, run, line, amount).status_code in (400, 409, 422)


def test_unattested_evidence_does_not_support_payment(client, pilot):
    invoice, line = pilot["invoice"]()
    pilot["evidence"](status="imported")
    run = run_invoice(client, pilot, invoice).json()
    assert Decimal(run["results"][0]["supported_amount"]) == 0
    assert approve(client, pilot, run, line).status_code in (400, 409, 422)


def test_draft_contract_and_wrong_date_do_not_authorize_payment(client, db, pilot):
    invoice, line = pilot["invoice"]()
    pilot["evidence"]()
    pilot["cv"].status = "draft"
    db.flush()
    response = run_invoice(client, pilot, invoice)
    assert response.status_code == 200, response.text
    result = response.json()["results"][0]
    assert Decimal(result["supported_amount"]) == 0
    assert Decimal(result["unverified_amount"]) == 40000
    assert approve(client, pilot, response.json(), line).status_code in (400, 409, 422)


def test_ambiguous_evidence_is_distinct_from_missing_evidence(client, pilot):
    invoice, _ = pilot["invoice"]()
    pilot["evidence"]("A")
    pilot["evidence"]("B")
    response = run_invoice(client, pilot, invoice)
    assert response.status_code == 200, response.text
    result = response.json()["results"][0]
    assert Decimal(result["supported_amount"]) == 0
    assert Decimal(result["unverified_amount"]) == 40000
    assert any(f["rule_code"] == "R005" for f in result["findings"])


def test_identical_run_retry_does_not_reserve_twice(client, db, pilot):
    invoice, _ = pilot["invoice"]()
    work = pilot["evidence"]()
    a = run_invoice(client, pilot, invoice, idempotency_key=pilot["id"]("request"))
    assert a.status_code == 200, a.text
    b = run_invoice(client, pilot, invoice, idempotency_key=pilot["id"]("request"))
    assert b.status_code == 200, b.text
    assert b.json()["id"] == a.json()["id"]
    allocations = (
        db.query(EvidenceAllocation)
        .filter(
            EvidenceAllocation.work_record_id == work.id,
            EvidenceAllocation.status.in_(["reserved", "consumed"]),
        )
        .all()
    )
    assert sum((row.quantity for row in allocations), Decimal(0)) == 145


def test_existing_export_download_is_scoped(client, pilot):
    invoice, line = pilot["invoice"]()
    pilot["evidence"]()
    run = run_invoice(client, pilot, invoice).json()
    approved = approve(client, pilot, run, line)
    assert approved.status_code == 200, approved.text
    batch = export(client, pilot, run)
    assert batch.status_code == 200, batch.text
    response = client.get(
        f"/api/v1/exports/{batch.json()['id']}/download",
        headers=pilot["headers"]("outsider"),
    )
    assert response.status_code in (403, 404)


def test_export_freezes_remaining_decisions(client, db, pilot):
    from app.models import InvoiceLine

    invoice, first_line = pilot["invoice"](hours="10", rate="240")
    pilot["evidence"](hours="10")
    second_line = InvoiceLine(
        id=pilot["id"]("second-line"),
        invoice_id=invoice.id,
        line_no=2,
        work_code="EQ-HIRE",
        service_date=first_line.service_date,
        quantity=Decimal(5),
        unit="hour",
        unit_price=Decimal(240),
        amount=Decimal(1200),
        work_reference="SHIFT-B",
    )
    db.add(second_line)
    pilot["evidence"]("B", hours="5", ref="SHIFT-B")
    db.flush()
    response = run_invoice(client, pilot, invoice)
    assert response.status_code == 200, response.text
    run = response.json()
    decision = approve(client, pilot, run, first_line, "2400")
    assert decision.status_code == 200, decision.text
    batch = export(client, pilot, run)
    assert batch.status_code == 200, batch.text
    assert batch.json()["total_minor"] == 240000
    current_run = client.get(
        f"/api/v1/reconciliation/runs/{run['id']}", headers=pilot["headers"]()
    ).json()
    assert approve(client, pilot, current_run, second_line, "1200").status_code == 409


def test_effective_rate_revision_preserves_historical_snapshot(client, db, pilot):
    from datetime import datetime

    from app.models import ContractVersion, RateLine

    earlier_date = datetime(2026, 10, 14, tzinfo=UTC)
    later_date = datetime(2026, 10, 15, tzinfo=UTC)
    before_invoice, _ = pilot["invoice"](
        "before", hours="10", rate="240", ref="BEFORE", when=earlier_date
    )
    pilot["evidence"]("before", hours="10", ref="BEFORE", when=earlier_date)
    earlier_response = run_invoice(client, pilot, before_invoice)
    assert earlier_response.status_code == 200, earlier_response.text
    earlier_run = earlier_response.json()
    version = ContractVersion(
        id=pilot["id"]("cv2"),
        contract_id=pilot["contract"].id,
        version_no=2,
        status="approved",
        effective_from=later_date,
        currency="USD",
        approved_by=pilot["users"]["contract_approver"],
    )
    db.add(version)
    db.flush()
    db.add(
        RateLine(
            contract_version_id=version.id,
            work_code="EQ-HIRE",
            unit="hour",
            rate=Decimal(255),
        )
    )
    db.flush()
    after_invoice, _ = pilot["invoice"](
        "after", hours="10", rate="255", ref="AFTER", when=later_date
    )
    pilot["evidence"]("after", hours="10", ref="AFTER", when=later_date)
    later_response = run_invoice(client, pilot, after_invoice)
    assert later_response.status_code == 200, later_response.text
    assert Decimal(earlier_run["results"][0]["supported_amount"]) == 2400
    assert Decimal(later_response.json()["results"][0]["supported_amount"]) == 2550
    historical = client.get(
        f"/api/v1/reconciliation/runs/{earlier_run['id']}", headers=pilot["headers"]()
    ).json()
    assert historical["input_snapshot"] == earlier_run["input_snapshot"]
    assert historical["input_hash"] == earlier_run["input_hash"]
    assert historical["results"] == earlier_run["results"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("created_by", None),
        ("input_snapshot", None),
        ("input_hash", None),
        ("input_snapshot", "{broken"),
        ("input_hash", "tampered"),
    ],
)
def test_legacy_or_tampered_runs_are_quarantined_before_decision_export_and_totals(
    client, db, pilot, field, value
):
    from app.models import Approval

    invoice, line = pilot["invoice"]()
    pilot["evidence"]()
    response = run_invoice(client, pilot, invoice)
    assert response.status_code == 200, response.text
    run = response.json()
    setattr(db.get(ReconciliationRun, run["id"]), field, value)
    db.flush()
    assert approve(client, pilot, run, line).status_code == 409
    # Represents pre-migration approvals from the old insecure implementation.
    db.add(
        Approval(
            run_id=run["id"],
            invoice_line_id=line.id,
            approver_id=pilot["users"]["finance_approver"],
            decision="approved",
            amount=Decimal(34800),
            reason="Legacy unverified decision",
            version=1,
        )
    )
    db.flush()
    assert export(client, pilot, run).status_code == 409
    detail = client.get(
        f"/api/v1/reconciliation/runs/{run['id']}", headers=pilot["headers"]()
    )
    assert detail.status_code == 200, detail.text
    assert detail.json()["legacy_quarantined"] is True
    assert detail.json()["is_current"] is False
    dashboard = client.get(
        "/api/v1/dashboard",
        params={"org_id": pilot["org"], "site_id": pilot["site"]},
        headers=pilot["headers"](),
    )
    assert dashboard.status_code == 200, dashboard.text
    totals = dashboard.json()["totals"]
    assert Decimal(totals["approved_amount"]) == 0
    assert Decimal(totals["supported_amount"]) == 0
    assert Decimal(totals["unverified_amount"]) == 40000


def test_missing_invoice_creator_blocks_legacy_approval_and_export(client, db, pilot):
    from app.models import Approval

    invoice, line = pilot["invoice"]()
    pilot["evidence"]()
    run = run_invoice(client, pilot, invoice).json()
    invoice.created_by = None
    db.flush()
    assert approve(client, pilot, run, line).status_code == 409
    db.add(
        Approval(
            run_id=run["id"],
            invoice_line_id=line.id,
            approver_id=pilot["users"]["finance_approver"],
            decision="approved",
            amount=Decimal(34800),
            reason="Legacy unverified decision",
            version=1,
        )
    )
    db.flush()
    assert export(client, pilot, run).status_code == 409
