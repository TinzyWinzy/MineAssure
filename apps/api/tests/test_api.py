from app.config import settings


def test_dev_login_and_bad_password(client, pilot):
    email = f"{pilot['users']['ap_analyst']}@demo.local"
    response = client.post(
        "/api/v1/auth/dev-login", json={"email": email, "password": "demo"}
    )
    assert response.status_code == 200
    assert response.json()["access_token"]
    assert (
        client.post(
            "/api/v1/auth/dev-login", json={"email": email, "password": "wrong"}
        ).status_code
        == 401
    )


def test_dev_login_disabled_in_production(client, monkeypatch):
    monkeypatch.setattr(settings, "environment", "production")
    assert (
        client.post(
            "/api/v1/auth/dev-login", json={"email": "anything", "password": "demo"}
        ).status_code
        == 403
    )


def test_business_routes_require_auth(client):
    for path in (
        "/api/v1/invoices",
        "/api/v1/contracts",
        "/api/v1/evidence",
        "/api/v1/audit",
    ):
        assert client.get(path).status_code == 401
    assert client.post("/api/v1/reconciliation/runs", json={}).status_code == 401


def test_revoked_membership_is_effective_before_token_expiry(client, db, pilot):
    from app.models import Membership

    headers = pilot["headers"]()
    db.query(Membership).filter(
        Membership.user_id == pilot["users"]["ap_analyst"]
    ).delete()
    db.flush()
    response = client.get(
        f"/api/v1/invoices?org_id={pilot['org']}&site_id={pilot['site']}",
        headers=headers,
    )
    assert response.status_code == 403
