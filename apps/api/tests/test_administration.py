"""Provisioning cannot borrow roles across sites or attach another tenant's users."""

from app.models import AuditEvent, Membership


def admin_headers(db, pilot):
    db.add(
        Membership(
            user_id=pilot["users"]["auditor"],
            org_id=pilot["org"],
            site_id=None,
            role="tenant_admin",
        )
    )
    db.flush()
    return pilot["headers"]("auditor")


def test_admin_can_create_site_user_and_revoke_live_access(client, db, pilot):
    headers = admin_headers(db, pilot)
    site = client.post(
        "/api/v1/admin/sites",
        headers=headers,
        json={"org_id": pilot["org"], "name": "Synthetic new site"},
    )
    assert site.status_code == 200, site.text
    body = {
        "org_id": pilot["org"],
        "site_id": site.json()["id"],
        "email": pilot["id"]("new") + "@demo.local",
        "password": "Synthetic-only-2026",
        "role": "ap_analyst",
    }
    created = client.post("/api/v1/admin/users", headers=headers, json=body)
    assert created.status_code == 200, created.text
    login = client.post(
        "/api/v1/auth/dev-login",
        json={"email": body["email"], "password": body["password"]},
    )
    assert login.status_code == 200
    user_headers = {"Authorization": "Bearer " + login.json()["access_token"]}
    params = {"org_id": pilot["org"], "site_id": site.json()["id"]}
    assert (
        client.get("/api/v1/invoices", params=params, headers=user_headers).status_code
        == 200
    )
    revoked = client.post(
        f"/api/v1/admin/memberships/{created.json()['membership_id']}/revoke",
        headers=headers,
    )
    assert revoked.status_code == 200, revoked.text
    assert (
        client.get("/api/v1/invoices", params=params, headers=user_headers).status_code
        == 403
    )
    events = db.query(AuditEvent).filter_by(org_id=pilot["org"]).all()
    assert {"site.created", "membership.created", "membership.revoked"} <= {
        e.action for e in events
    }
    assert all(body["password"] not in (e.new_value or "") for e in events)


def test_provisioning_does_not_reset_existing_password(client, db, pilot):
    headers = admin_headers(db, pilot)
    body = {
        "org_id": pilot["org"],
        "site_id": pilot["site"],
        "email": f"{pilot['users']['ap_analyst']}@demo.local",
        "password": "Synthetic-only-2026",
        "role": "finance_approver",
    }
    assert (
        client.post("/api/v1/admin/users", headers=headers, json=body).status_code
        == 409
    )
    login = client.post(
        "/api/v1/auth/dev-login", json={"email": body["email"], "password": "demo"}
    )
    assert login.status_code == 200


def test_admin_grants_are_idempotent_and_tenant_scoped(client, db, pilot):
    headers = admin_headers(db, pilot)
    body = {
        "org_id": pilot["org"],
        "site_id": pilot["other_site"],
        "user_id": pilot["users"]["ap_analyst"],
        "role": "ap_analyst",
    }
    first = client.post("/api/v1/admin/memberships", headers=headers, json=body)
    second = client.post("/api/v1/admin/memberships", headers=headers, json=body)
    assert first.status_code == second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    body["user_id"] = pilot["outsider"]
    assert (
        client.post("/api/v1/admin/memberships", headers=headers, json=body).status_code
        == 404
    )
    own = (
        db.query(Membership)
        .filter_by(user_id=pilot["users"]["auditor"], role="tenant_admin")
        .one()
    )
    assert (
        client.post(
            f"/api/v1/admin/memberships/{own.id}/revoke", headers=headers
        ).status_code
        == 409
    )


def test_site_admin_cannot_create_tenant_wide_resources(client, db, pilot):
    db.add(
        Membership(
            user_id=pilot["users"]["auditor"],
            org_id=pilot["org"],
            site_id=pilot["site"],
            role="tenant_admin",
        )
    )
    db.flush()
    response = client.post(
        "/api/v1/admin/sites",
        headers=pilot["headers"]("auditor"),
        json={"org_id": pilot["org"], "name": "Disallowed site"},
    )
    assert response.status_code == 403
    response = client.post(
        "/api/v1/admin/sites",
        headers=pilot["headers"](),
        json={"org_id": pilot["org"], "name": "Disallowed site"},
    )
    assert response.status_code == 403
