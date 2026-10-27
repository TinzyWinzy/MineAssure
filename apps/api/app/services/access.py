"""Scoped authorization and append-only application audit helpers."""

import json
import uuid
from contextvars import ContextVar

from fastapi import HTTPException

from app.auth import authorize
from app.models import AuditEvent, Site

READ_ROLES = (
    "tenant_admin",
    "contract_preparer",
    "contract_approver",
    "operations_verifier",
    "ap_analyst",
    "finance_approver",
    "auditor",
)
request_id_context: ContextVar[str | None] = ContextVar("request_id", default=None)


def scope(db, user, org_id, site_id, *roles):
    authorize(user, org_id, site_id, *(roles or READ_ROLES))
    site = db.get(Site, site_id) if site_id else None
    if site_id and (not site or site.org_id != org_id):
        raise HTTPException(404, "Site not found")


def entity_scope(db, user, entity, *roles):
    if entity is None:
        raise HTTPException(404, "Record not found")
    scope(db, user, entity.org_id, entity.site_id, *roles)
    return entity


def audit(db, user, entity, action, details=None, entity_type=None):
    db.add(
        AuditEvent(
            org_id=entity.org_id,
            site_id=getattr(entity, "site_id", None),
            actor_id=user.id,
            action=action,
            entity_type=entity_type or entity.__tablename__,
            entity_id=entity.id,
            new_value=json.dumps(details or {}, default=str, sort_keys=True),
            request_id=request_id_context.get() or str(uuid.uuid4()),
        )
    )


def fields(row, *names):
    result = {}
    for name in names:
        value = getattr(row, name)
        result[name] = (
            value.isoformat()
            if hasattr(value, "isoformat")
            else str(value)
            if hasattr(value, "as_tuple")
            else value
        )
    return result
