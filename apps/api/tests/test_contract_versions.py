from decimal import Decimal

from app.models import ContractVersion, RateLine


def test_revision_workflow_preserves_approved_terms(client, db, pilot):
    url = f"/api/v1/contracts/{pilot['contract'].id}/versions"
    body = {"effective_from": "2026-10-15T00:00:00Z", "rate": "255"}
    response = client.post(
        url, json=body, headers=pilot["headers"]("contract_preparer")
    )
    assert response.status_code == 200, response.text
    revision = response.json()
    assert revision["version_no"] == 2 and revision["status"] == "draft"
    assert (
        client.post(
            url, json=body, headers=pilot["headers"]("contract_preparer")
        ).status_code
        == 409
    )
    approve = f"/api/v1/contracts/{pilot['contract'].id}/approve"
    stale = client.post(
        approve,
        params={"version_id": pilot["cv"].id},
        headers=pilot["headers"]("contract_approver"),
    )
    assert stale.status_code == 409
    approved = client.post(
        approve,
        params={"version_id": revision["id"]},
        headers=pilot["headers"]("contract_approver"),
    )
    assert approved.status_code == 200, approved.text
    db.refresh(pilot["cv"])
    assert pilot["cv"].status == "approved"
    assert db.query(RateLine).filter_by(
        contract_version_id=pilot["cv"].id
    ).one().rate == Decimal(240)
    assert db.get(ContractVersion, revision["id"]).content_hash
    history = client.get(url, headers=pilot["headers"]("auditor"))
    assert history.status_code == 200
    assert [v["version_no"] for v in history.json()] == [2, 1]


def test_revision_rejects_wrong_role_foreign_tenant_and_retroactive_dates(
    client, pilot
):
    url = f"/api/v1/contracts/{pilot['contract'].id}/versions"
    body = {"effective_from": "2026-10-15", "rate": "255"}
    assert client.post(url, json=body, headers=pilot["headers"]()).status_code == 403
    assert client.get(url, headers=pilot["headers"]("outsider")).status_code == 403
    body["effective_from"] = "2025-01-01"
    assert (
        client.post(
            url, json=body, headers=pilot["headers"]("contract_preparer")
        ).status_code
        == 422
    )
