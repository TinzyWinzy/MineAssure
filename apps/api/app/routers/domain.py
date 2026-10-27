"""Bounded pilot input workflows; all authority is derived from current DB grants."""

import hashlib
import json
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.auth import get_current_user, memberships_of
from app.db import get_db
from app.models import (
    AuditEvent,
    Contract,
    Contractor,
    ContractVersion,
    Invoice,
    InvoiceLine,
    Membership,
    RateLine,
    ReconciliationRun,
    Site,
    User,
    WorkRecord,
)
from app.services.access import audit, entity_scope, fields, scope

router = APIRouter(tags=["inputs"])
Quantity = Annotated[
    Decimal,
    Field(
        gt=0, le=Decimal(1000000), max_digits=18, decimal_places=6, allow_inf_nan=False
    ),
]
Money = Annotated[
    Decimal,
    Field(
        ge=0, le=Decimal(1000000), max_digits=18, decimal_places=6, allow_inf_nan=False
    ),
]
Text = Annotated[str, Field(min_length=1, max_length=200)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Scoped(StrictModel):
    org_id: Text
    site_id: Text


class ContractIn(Scoped):
    contractor_id: Text
    title: Text
    effective_from: datetime
    effective_to: datetime | None = None
    rate: Money
    work_code: Text = "EQ-HIRE"
    cap_hours: Quantity | None = None


class ContractorIn(Scoped):
    name: Text


class VersionIn(StrictModel):
    effective_from: datetime
    effective_to: datetime | None = None
    rate: Money
    work_code: Text = "EQ-HIRE"
    cap_hours: Quantity | None = None


@router.post("/contractors")
def create_contractor(
    body: ContractorIn, user=Depends(get_current_user), db: Session = Depends(get_db)
):
    scope(db, user, body.org_id, body.site_id, "tenant_admin")
    supplier = Contractor(org_id=body.org_id, name=body.name)
    db.add(supplier)
    db.flush()
    audit(db, user, supplier, "contractor.registered", {"name": body.name})
    db.commit()
    return fields(supplier, "id", "name")


class EvidenceIn(Scoped):
    contract_id: Text
    work_code: Text = "EQ-HIRE"
    work_reference: Text
    quantity: Quantity
    service_date: datetime
    unit: str = "hour"


class LineIn(StrictModel):
    work_code: Text = "EQ-HIRE"
    service_date: datetime
    quantity: Quantity
    unit_price: Money
    work_reference: Text | None = None
    unit: str = "hour"
    description: str = Field(default="Equipment hire", max_length=500)


class InvoiceIn(Scoped):
    contract_id: Text
    supplier_invoice_no: Text
    lines: list[LineIn] = Field(min_length=1, max_length=500)


def utc(value):
    return value.replace(tzinfo=UTC) if value and value.tzinfo is None else value


def contract_for(db, user, contract_id, org_id, site_id, *roles):
    scope(db, user, org_id, site_id, *roles)
    contract = db.get(Contract, contract_id)
    if not contract or contract.org_id != org_id or contract.site_id != site_id:
        raise HTTPException(404, "Contract not found")
    return contract


@router.get("/sites")
def sites(user=Depends(get_current_user), db: Session = Depends(get_db)):
    grants = memberships_of(user)
    return [
        fields(s, "id", "org_id", "name")
        for s in db.query(Site).order_by(Site.name).all()
        if any(
            m["org_id"] == s.org_id
            and (m.get("site_id") is None or m["site_id"] == s.id)
            and m["role"] != "partner_readonly"
            for m in grants
        )
    ]


@router.get("/contractors")
def contractors(
    org_id: str,
    site_id: str,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    scope(db, user, org_id, site_id)
    return [
        fields(c, "id", "name")
        for c in db.query(Contractor).filter_by(org_id=org_id).limit(200)
    ]


@router.get("/contracts")
def contracts(
    org_id: str,
    site_id: str,
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    scope(db, user, org_id, site_id)
    out = []
    for c in (
        db.query(Contract)
        .filter_by(org_id=org_id, site_id=site_id)
        .order_by(Contract.created_at.desc(), Contract.id)
        .offset(offset)
        .limit(limit)
    ):
        cv = (
            db.query(ContractVersion)
            .filter_by(contract_id=c.id)
            .order_by(ContractVersion.version_no.desc())
            .first()
        )
        rate = (
            db.query(RateLine).filter_by(contract_version_id=cv.id).first()
            if cv
            else None
        )
        out.append(
            {
                **fields(c, "id", "title", "contractor_id"),
                "status": cv.status if cv else "draft",
                "version_id": cv.id if cv else None,
                "version_no": cv.version_no if cv else 0,
                "rate": str(rate.rate) if rate else None,
                "work_code": rate.work_code if rate else None,
                "effective_from": cv.effective_from.isoformat() if cv else None,
                "created_by": cv.created_by if cv else None,
            }
        )
    return out


@router.post("/contracts")
def create_contract(
    body: ContractIn, user=Depends(get_current_user), db: Session = Depends(get_db)
):
    scope(db, user, body.org_id, body.site_id, "contract_preparer", "tenant_admin")
    supplier = db.get(Contractor, body.contractor_id)
    if not supplier or supplier.org_id != body.org_id:
        raise HTTPException(404, "Contractor not found")
    if body.effective_to and utc(body.effective_to) < utc(body.effective_from):
        raise HTTPException(422, "Invalid effective date range")
    contract = Contract(
        org_id=body.org_id,
        site_id=body.site_id,
        contractor_id=body.contractor_id,
        title=body.title,
    )
    db.add(contract)
    db.flush()
    cv = ContractVersion(
        contract_id=contract.id,
        version_no=1,
        created_by=user.id,
        effective_from=utc(body.effective_from),
        effective_to=utc(body.effective_to),
        currency="USD",
        status="draft",
    )
    db.add(cv)
    db.flush()
    db.add(
        RateLine(
            contract_version_id=cv.id,
            work_code=body.work_code,
            unit="hour",
            rate=body.rate,
            cap_hours=body.cap_hours,
        )
    )
    audit(db, user, contract, "contract.drafted", body.model_dump())
    db.commit()
    return {"id": contract.id, "version_id": cv.id, "status": cv.status}


@router.post("/contracts/{contract_id}/approve")
def approve_contract(
    contract_id: str,
    version_id: str | None = None,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    contract = entity_scope(
        db, user, db.get(Contract, contract_id), "contract_approver"
    )
    db.query(Contract).filter_by(id=contract.id).with_for_update().one()
    cv = (
        db.query(ContractVersion)
        .filter_by(contract_id=contract.id)
        .order_by(ContractVersion.version_no.desc())
        .with_for_update()
        .first()
    )
    if not cv or (version_id is not None and cv.id != version_id):
        raise HTTPException(409, "Contract version changed; refresh before approval")
    if cv.status != "draft":
        raise HTTPException(409, "Only a draft version can be approved")
    edited_version = any(
        json.loads(event.new_value or "{}").get("version_id") == cv.id
        for event in db.query(AuditEvent).filter_by(
            entity_id=contract.id, actor_id=user.id, action="contract.draft_updated"
        )
    )
    if cv.created_by == user.id or edited_version:
        raise HTTPException(403, "Contract preparer cannot approve their own version")
    rates = db.query(RateLine).filter_by(contract_version_id=cv.id).all()
    snapshot = {
        "effective_from": str(cv.effective_from),
        "effective_to": str(cv.effective_to),
        "currency": cv.currency,
        "rates": [fields(r, "work_code", "unit", "rate", "cap_hours") for r in rates],
    }
    cv.content_hash = hashlib.sha256(
        json.dumps(snapshot, sort_keys=True).encode()
    ).hexdigest()
    cv.status, cv.approved_by, cv.approved_at = "approved", user.id, datetime.now(UTC)
    contract.revision += 1
    audit(
        db,
        user,
        contract,
        "contract.approved",
        {"version_id": cv.id, "content_hash": cv.content_hash},
    )
    db.commit()
    return {"id": contract.id, "version_id": cv.id, "status": cv.status}


@router.get("/contracts/{contract_id}/versions")
def contract_versions(
    contract_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)
):
    contract = entity_scope(db, user, db.get(Contract, contract_id))
    return [
        {
            **fields(
                v,
                "id",
                "version_no",
                "status",
                "effective_from",
                "effective_to",
                "created_by",
                "approved_by",
                "approved_at",
                "content_hash",
            ),
            "rates": [
                fields(r, "work_code", "unit", "rate", "cap_hours")
                for r in db.query(RateLine).filter_by(contract_version_id=v.id)
            ],
        }
        for v in db.query(ContractVersion)
        .filter_by(contract_id=contract.id)
        .order_by(ContractVersion.version_no.desc())
    ]


@router.post("/contracts/{contract_id}/versions")
def create_contract_version(
    contract_id: str,
    body: VersionIn,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    contract = entity_scope(
        db, user, db.get(Contract, contract_id), "contract_preparer", "tenant_admin"
    )
    db.query(Contract).filter_by(id=contract.id).with_for_update().one()
    latest = (
        db.query(ContractVersion)
        .filter_by(contract_id=contract.id)
        .order_by(ContractVersion.version_no.desc())
        .first()
    )
    if latest and latest.status == "draft":
        raise HTTPException(
            409, "Approve the existing draft before creating a revision"
        )
    if body.effective_to and utc(body.effective_to) < utc(body.effective_from):
        raise HTTPException(422, "Invalid effective date range")
    if latest and utc(body.effective_from) <= utc(latest.effective_from):
        raise HTTPException(422, "A revision must begin after the previous version")
    cv = ContractVersion(
        contract_id=contract.id,
        version_no=(latest.version_no + 1 if latest else 1),
        created_by=user.id,
        effective_from=utc(body.effective_from),
        effective_to=utc(body.effective_to),
        currency="USD",
        status="draft",
    )
    db.add(cv)
    db.flush()
    db.add(
        RateLine(
            contract_version_id=cv.id,
            work_code=body.work_code,
            unit="hour",
            rate=body.rate,
            cap_hours=body.cap_hours,
        )
    )
    audit(
        db,
        user,
        contract,
        "contract.version_drafted",
        {"version_id": cv.id, **body.model_dump()},
    )
    contract.revision += 1
    db.commit()
    return {"id": cv.id, "version_no": cv.version_no, "status": cv.status}


def add_evidence(db, user, body):
    c = contract_for(
        db,
        user,
        body.contract_id,
        body.org_id,
        body.site_id,
        "operations_verifier",
        "tenant_admin",
    )
    if body.unit != "hour":
        raise HTTPException(422, "Pilot supports hour units only")
    work = WorkRecord(
        org_id=body.org_id,
        site_id=body.site_id,
        contract_id=c.id,
        contractor_id=c.contractor_id,
        work_code=body.work_code,
        work_reference=body.work_reference,
        quantity=body.quantity,
        unit=body.unit,
        service_date=utc(body.service_date),
        status="imported",
        created_by=user.id,
    )
    db.add(work)
    db.flush()
    audit(db, user, work, "evidence.registered", body.model_dump())
    return work


@router.post("/evidence")
def create_evidence(
    body: EvidenceIn, user=Depends(get_current_user), db: Session = Depends(get_db)
):
    work = add_evidence(db, user, body)
    db.commit()
    return fields(work, "id", "status", "work_reference", "quantity")


@router.get("/evidence")
def evidence(
    org_id: str,
    site_id: str,
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    scope(db, user, org_id, site_id)
    return [
        fields(
            w,
            "id",
            "work_reference",
            "work_code",
            "quantity",
            "unit",
            "service_date",
            "status",
            "attested_by",
            "contract_id",
        )
        for w in db.query(WorkRecord)
        .filter_by(org_id=org_id, site_id=site_id)
        .order_by(WorkRecord.created_at.desc(), WorkRecord.id)
        .offset(offset)
        .limit(limit)
    ]


@router.post("/evidence/{work_id}/attest")
def attest(work_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    work = entity_scope(
        db,
        user,
        db.query(WorkRecord).filter_by(id=work_id).with_for_update().first(),
        "operations_verifier",
    )
    if work.status != "imported":
        raise HTTPException(409, "Only imported records may be attested")
    if (
        work.created_by == user.id
        or db.query(AuditEvent)
        .filter_by(entity_id=work.id, actor_id=user.id, action="evidence.updated")
        .first()
    ):
        raise HTTPException(
            403, "An independent operations verifier must attest this record"
        )
    work.status, work.attested_by, work.attested_at = (
        "attested",
        user.id,
        datetime.now(UTC),
    )
    work.revision += 1
    audit(
        db,
        user,
        work,
        "evidence.attested",
        {"quantity": str(work.quantity), "source_actor": work.created_by},
    )
    db.commit()
    return fields(work, "id", "status", "attested_by")


def add_invoice(db, user, body):
    c = contract_for(
        db,
        user,
        body.contract_id,
        body.org_id,
        body.site_id,
        "ap_analyst",
        "tenant_admin",
    )
    if (
        db.query(Invoice)
        .filter_by(
            org_id=body.org_id,
            contractor_id=c.contractor_id,
            supplier_invoice_no=body.supplier_invoice_no,
        )
        .first()
    ):
        raise HTTPException(
            409,
            "Duplicate supplier invoice reference; investigate the existing invoice",
        )
    invoice = Invoice(
        org_id=body.org_id,
        site_id=body.site_id,
        contract_id=c.id,
        contractor_id=c.contractor_id,
        supplier_invoice_no=body.supplier_invoice_no,
        currency="USD",
        created_by=user.id,
    )
    db.add(invoice)
    db.flush()
    for n, line in enumerate(body.lines, 1):
        if line.unit != "hour":
            raise HTTPException(422, "Pilot supports hour units only")
        db.add(
            InvoiceLine(
                invoice_id=invoice.id,
                line_no=n,
                work_code=line.work_code,
                quantity=line.quantity,
                unit=line.unit,
                unit_price=line.unit_price,
                amount=(line.quantity * line.unit_price).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                ),
                service_date=utc(line.service_date),
                work_reference=line.work_reference,
                description=line.description,
            )
        )
    invoice.fingerprint = hashlib.sha256(
        json.dumps(body.model_dump(mode="json"), sort_keys=True).encode()
    ).hexdigest()
    audit(
        db,
        user,
        invoice,
        "invoice.registered",
        {
            "supplier_invoice_no": invoice.supplier_invoice_no,
            "lines": len(body.lines),
            "fingerprint": invoice.fingerprint,
        },
    )
    return invoice


@router.post("/invoices")
def create_invoice(
    body: InvoiceIn, user=Depends(get_current_user), db: Session = Depends(get_db)
):
    invoice = add_invoice(db, user, body)
    db.commit()
    return {
        "id": invoice.id,
        "supplier_invoice_no": invoice.supplier_invoice_no,
        "status": invoice.status,
    }


def invoice_row(db, invoice):
    supplier = db.get(Contractor, invoice.contractor_id)
    lines = db.query(InvoiceLine).filter_by(invoice_id=invoice.id).all()
    return {
        **fields(
            invoice,
            "id",
            "supplier_invoice_no",
            "status",
            "currency",
            "contract_id",
            "created_at",
        ),
        "contractor_name": supplier.name if supplier else "Unknown",
        "total": str(sum((line.amount for line in lines), Decimal(0))),
    }


@router.get("/invoices")
def invoices(
    org_id: str,
    site_id: str,
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    scope(db, user, org_id, site_id)
    return [
        invoice_row(db, i)
        for i in db.query(Invoice)
        .filter_by(org_id=org_id, site_id=site_id)
        .order_by(Invoice.created_at.desc(), Invoice.id)
        .offset(offset)
        .limit(limit)
    ]


@router.get("/invoices/{invoice_id}")
def invoice_detail(
    invoice_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)
):
    invoice = entity_scope(db, user, db.get(Invoice, invoice_id))
    run = (
        db.query(ReconciliationRun)
        .filter_by(invoice_id=invoice.id, is_current=True)
        .first()
    )
    from app.routers.persistence import _run_out

    return {
        **invoice_row(db, invoice),
        "lines": [
            fields(
                line,
                "id",
                "line_no",
                "work_code",
                "description",
                "quantity",
                "unit",
                "unit_price",
                "amount",
                "work_reference",
                "service_date",
            )
            for line in db.query(InvoiceLine)
            .filter_by(invoice_id=invoice.id)
            .order_by(InvoiceLine.line_no)
        ],
        "current_run": _run_out(db, run) if run else None,
    }


@router.get("/admin/users")
def users(
    org_id: str,
    site_id: str,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    scope(db, user, org_id, site_id, "tenant_admin")
    return [
        {
            "id": m.user_id,
            "membership_id": m.id,
            "email": db.get(User, m.user_id).email,
            "role": m.role,
            "site_id": m.site_id,
        }
        for m in db.query(Membership).filter_by(org_id=org_id).all()
        if m.site_id in (site_id, None)
        or any(
            grant["org_id"] == org_id
            and grant.get("site_id") is None
            and grant["role"] == "tenant_admin"
            for grant in memberships_of(user)
        )
    ]
