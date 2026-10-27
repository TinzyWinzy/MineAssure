"""Tenant administrators provision local pilot identities and scoped grants."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field, field_validator
from sqlalchemy.orm import Session

from app.auth import authorize, get_current_user, hash_password
from app.db import get_db
from app.models import Membership, Organisation, Site, User
from app.routers.domain import Scoped, StrictModel, Text
from app.services.access import audit, fields, scope

router = APIRouter(prefix="/admin", tags=["administration"])
Role = Literal[
    "tenant_admin",
    "contract_preparer",
    "contract_approver",
    "operations_verifier",
    "ap_analyst",
    "finance_approver",
    "auditor",
    "partner_readonly",
]


def tenant_admin(db, user, org_id):
    # A site grant cannot be used to create sites or tenant-wide grants.
    authorize(user, org_id, None, "tenant_admin")
    org = db.query(Organisation).filter_by(id=org_id).with_for_update().first()
    if not org:
        raise HTTPException(404, "Organisation not found")
    return org


class SiteIn(StrictModel):
    org_id: Text
    name: Text


class UserIn(Scoped):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=12, max_length=72)
    role: Role

    @field_validator("email")
    @classmethod
    def email_valid(cls, value):
        value = value.lower()
        if value.count("@") != 1 or any(c.isspace() for c in value):
            raise ValueError("Enter a valid email address")
        local, domain = value.split("@")
        if (
            not local
            or "." not in domain
            or domain.startswith(".")
            or domain.endswith(".")
        ):
            raise ValueError("Enter a valid email address")
        return value

    @field_validator("password")
    @classmethod
    def password_valid(cls, value):
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must fit within 72 UTF-8 bytes")
        return value


class GrantIn(Scoped):
    user_id: Text
    role: Role


@router.post("/sites")
def create_site(
    body: SiteIn, user=Depends(get_current_user), db: Session = Depends(get_db)
):
    tenant_admin(db, user, body.org_id)
    site = Site(org_id=body.org_id, name=body.name)
    db.add(site)
    db.flush()
    audit(db, user, site, "site.created", {"name": body.name})
    db.commit()
    return fields(site, "id", "org_id", "name")


@router.post("/users")
def create_user(
    body: UserIn, user=Depends(get_current_user), db: Session = Depends(get_db)
):
    scope(db, user, body.org_id, body.site_id, "tenant_admin")
    tenant_admin(db, user, body.org_id)
    if db.query(User).filter_by(email=body.email).first():
        raise HTTPException(
            409, "Account already exists; use an existing tenant user grant"
        )
    account = User(email=body.email, hashed_password=hash_password(body.password))
    db.add(account)
    db.flush()
    grant = Membership(
        user_id=account.id, org_id=body.org_id, site_id=body.site_id, role=body.role
    )
    db.add(grant)
    db.flush()
    audit(
        db,
        user,
        grant,
        "membership.created",
        {"user_id": account.id, "role": body.role},
    )
    db.commit()
    return {"id": account.id, "email": account.email, "membership_id": grant.id}


@router.post("/memberships")
def grant_membership(
    body: GrantIn, user=Depends(get_current_user), db: Session = Depends(get_db)
):
    scope(db, user, body.org_id, body.site_id, "tenant_admin")
    tenant_admin(db, user, body.org_id)
    # Do not disclose or attach identities belonging only to another tenant.
    if (
        not db.query(Membership)
        .filter_by(org_id=body.org_id, user_id=body.user_id)
        .first()
    ):
        raise HTTPException(404, "Tenant user not found")
    prior = db.query(Membership).filter_by(**body.model_dump()).first()
    if prior:
        return fields(prior, "id", "user_id", "site_id", "role")
    grant = Membership(**body.model_dump())
    db.add(grant)
    db.flush()
    audit(db, user, grant, "membership.created", body.model_dump())
    db.commit()
    return fields(grant, "id", "user_id", "site_id", "role")


@router.post("/memberships/{membership_id}/revoke")
def revoke_membership(
    membership_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)
):
    grant = db.get(Membership, membership_id)
    if not grant:
        raise HTTPException(404, "Membership not found")
    tenant_admin(db, user, grant.org_id)
    if grant.user_id == user.id:
        raise HTTPException(409, "An administrator cannot revoke their own access")
    audit(
        db,
        user,
        grant,
        "membership.revoked",
        fields(grant, "user_id", "site_id", "role"),
    )
    db.delete(grant)
    db.commit()
    return {"status": "revoked"}
