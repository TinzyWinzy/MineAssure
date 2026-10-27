"""Scoped record associations and optimistic CRUD before financial finalization."""

import hashlib
import json
from decimal import ROUND_HALF_UP, Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth import get_current_user, memberships_of
from app.db import get_db
from app.models import (
    Contract,
    Contractor,
    ContractVariation,
    ContractVersion,
    EvidenceAllocation,
    ImportBatch,
    Invoice,
    InvoiceLine,
    JobRun,
    RateLine,
    ReconciliationRun,
    WorkRecord,
)
from app.routers.domain import (
    ContractIn,
    ContractorIn,
    EvidenceIn,
    InvoiceIn,
    contract_for,
    invoice_row,
    utc,
)
from app.services.access import audit, fields, scope

router = APIRouter(tags=["records"])
MODELS = {
    "contractors": Contractor,
    "contracts": Contract,
    "evidence": WorkRecord,
    "invoices": Invoice,
}
ROLES = {
    "contractors": ("tenant_admin",),
    "contracts": ("contract_preparer", "tenant_admin"),
    "evidence": ("operations_verifier", "tenant_admin"),
    "invoices": ("ap_analyst", "tenant_admin"),
}


def record_for(db, user, kind, record_id, org_id, site_id, *, write=False):
    if kind not in MODELS:
        raise HTTPException(404, "Record type not found")
    scope(db, user, org_id, site_id, *(ROLES[kind] if write else ()))
    query = db.query(MODELS[kind]).filter_by(id=record_id)
    record = (query.with_for_update() if write else query).first()
    if (
        not record
        or record.org_id != org_id
        or (kind != "contractors" and record.site_id != site_id)
    ):
        raise HTTPException(404, "Record not found in selected site")
    return record


def guard_revision(record, expected):
    if record.revision != expected:
        raise HTTPException(409, "Record changed; refresh before editing or deleting")


def latest_version(db, contract_id):
    return (
        db.query(ContractVersion)
        .filter_by(contract_id=contract_id)
        .order_by(ContractVersion.version_no.desc())
        .first()
    )


def lock_reason(db, kind, record):
    if kind == "invoices":
        if db.query(ReconciliationRun).filter_by(invoice_id=record.id).first():
            return "This invoice has reconciliation history. Its original lines and associations are retained."
        for job in db.query(JobRun).filter(
            JobRun.org_id == record.org_id, JobRun.status.in_(["queued", "running"])
        ):
            if json.loads(job.payload or "{}").get("invoice_id") == record.id:
                return "A background job is using this invoice. Wait for processing before changing it."
    if kind == "evidence" and (
        record.status != "imported"
        or db.query(EvidenceAllocation).filter_by(work_record_id=record.id).first()
    ):
        return "Attested or allocated evidence is retained as a historical source. Register a corrected independent record."
    if kind == "contracts":
        version = latest_version(db, record.id)
        if not version or version.status != "draft":
            return "Approved terms are immutable. Draft a new effective-dated revision to change pricing."
    return None


def relation(db, model, record_id, *names):
    row = db.get(model, record_id) if record_id else None
    return fields(row, "id", *names) if row else None


@router.get("/records/{kind}/{record_id}")
def record_detail(
    kind: str,
    record_id: str,
    org_id: str,
    site_id: str,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = record_for(db, user, kind, record_id, org_id, site_id)
    reason = lock_reason(db, kind, row)
    can_edit = any(
        m["org_id"] == org_id
        and m.get("site_id") in (None, site_id)
        and m["role"] in ROLES[kind]
        for m in memberships_of(user)
    )
    associations = {}
    if kind == "contractors":
        item = fields(row, "id", "name", "revision")
        associations["contracts"] = [
            fields(c, "id", "title")
            for c in db.query(Contract).filter_by(contractor_id=row.id, site_id=site_id)
        ]
        associations["invoices"] = [
            invoice_row(db, i)
            for i in db.query(Invoice).filter_by(contractor_id=row.id, site_id=site_id)
        ]
    elif kind == "contracts":
        version = latest_version(db, row.id)
        rate = (
            db.query(RateLine).filter_by(contract_version_id=version.id).first()
            if version
            else None
        )
        item = {
            **fields(row, "id", "title", "contractor_id", "revision"),
            "effective_from": version.effective_from.isoformat() if version else None,
            "effective_to": version.effective_to.isoformat()
            if version and version.effective_to
            else None,
            "rate": str(rate.rate) if rate else "0",
            "work_code": rate.work_code if rate else "EQ-HIRE",
            "cap_hours": str(rate.cap_hours)
            if rate and rate.cap_hours is not None
            else None,
            "status": version.status if version else "draft",
        }
        associations["contractor"] = relation(db, Contractor, row.contractor_id, "name")
        associations["invoices"] = [
            invoice_row(db, i)
            for i in db.query(Invoice).filter_by(contract_id=row.id, site_id=site_id)
        ]
        associations["evidence"] = [
            fields(w, "id", "work_reference", "quantity", "status")
            for w in db.query(WorkRecord).filter_by(contract_id=row.id, site_id=site_id)
        ]
    elif kind == "evidence":
        item = fields(
            row,
            "id",
            "contract_id",
            "work_reference",
            "work_code",
            "quantity",
            "unit",
            "service_date",
            "status",
            "revision",
            "attested_by",
            "import_batch_id",
        )
        associations["contract"] = relation(db, Contract, row.contract_id, "title")
        associations["contractor"] = relation(db, Contractor, row.contractor_id, "name")
        associations["allocations"] = [
            fields(
                a,
                "id",
                "invoice_line_id",
                "reconciliation_run_id",
                "quantity",
                "status",
            )
            for a in db.query(EvidenceAllocation).filter_by(work_record_id=row.id)
        ]
        associations["import"] = relation(
            db, ImportBatch, row.import_batch_id, "filename", "sha256", "status"
        )
    else:
        item = {
            **invoice_row(db, row),
            "revision": row.revision,
            "lines": [
                fields(
                    line,
                    "id",
                    "work_code",
                    "description",
                    "service_date",
                    "quantity",
                    "unit",
                    "unit_price",
                    "work_reference",
                    "amount",
                )
                for line in db.query(InvoiceLine)
                .filter_by(invoice_id=row.id)
                .order_by(InvoiceLine.line_no)
            ],
        }
        associations["contract"] = relation(db, Contract, row.contract_id, "title")
        associations["contractor"] = relation(db, Contractor, row.contractor_id, "name")
        associations["import"] = relation(
            db, ImportBatch, row.import_batch_id, "filename", "sha256", "status"
        )
        associations["runs"] = [
            fields(run, "id", "is_current", "status", "input_hash", "completed_at")
            for run in db.query(ReconciliationRun)
            .filter_by(invoice_id=row.id)
            .order_by(ReconciliationRun.started_at.desc())
        ]
    return {
        "kind": kind,
        "item": item,
        "associations": associations,
        "can_edit": can_edit and reason is None,
        "can_delete": can_edit and reason is None,
        "locked_reason": reason
        or (None if can_edit else "Your role has read-only access to this record."),
    }


@router.put("/contractors/{record_id}")
def update_contractor(
    record_id: str,
    body: ContractorIn,
    expected_revision: int = Query(ge=1),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = record_for(
        db, user, "contractors", record_id, body.org_id, body.site_id, write=True
    )
    guard_revision(row, expected_revision)
    old = fields(row, "name", "revision")
    row.name, row.revision = body.name, row.revision + 1
    audit(
        db,
        user,
        row,
        "contractor.updated",
        {"before": old, "after": fields(row, "name", "revision")},
    )
    db.commit()
    return fields(row, "id", "name", "revision")


@router.put("/contracts/{record_id}")
def update_contract(
    record_id: str,
    body: ContractIn,
    expected_revision: int = Query(ge=1),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = record_for(
        db, user, "contracts", record_id, body.org_id, body.site_id, write=True
    )
    guard_revision(row, expected_revision)
    if reason := lock_reason(db, "contracts", row):
        raise HTTPException(409, reason)
    supplier = db.get(Contractor, body.contractor_id)
    if not supplier or supplier.org_id != row.org_id:
        raise HTTPException(404, "Contractor not found")
    version = latest_version(db, row.id)
    approved = (
        db.query(ContractVersion)
        .filter_by(contract_id=row.id, status="approved")
        .order_by(ContractVersion.effective_from.desc())
        .first()
    )
    if approved and (
        body.contractor_id != row.contractor_id or body.title != row.title
    ):
        raise HTTPException(
            409,
            "Historical contract identity cannot be reassociated; edit draft pricing only",
        )
    if body.effective_to and utc(body.effective_to) < utc(body.effective_from):
        raise HTTPException(422, "Invalid effective date range")
    if approved and utc(body.effective_from) <= utc(approved.effective_from):
        raise HTTPException(422, "Revision must start after approved terms")
    if body.contractor_id != row.contractor_id and (
        db.query(Invoice).filter_by(contract_id=row.id).first()
        or db.query(WorkRecord).filter_by(contract_id=row.id).first()
    ):
        raise HTTPException(
            409, "Contract has linked records; supplier cannot be changed"
        )
    rate = db.query(RateLine).filter_by(contract_version_id=version.id).one()
    row.title, row.contractor_id = body.title, body.contractor_id
    version.effective_from, version.effective_to = (
        utc(body.effective_from),
        utc(body.effective_to),
    )
    rate.rate, rate.work_code, rate.cap_hours = (
        body.rate,
        body.work_code,
        body.cap_hours,
    )
    row.revision += 1
    audit(
        db,
        user,
        row,
        "contract.draft_updated",
        {"version_id": version.id, **body.model_dump()},
    )
    db.commit()
    return {"id": row.id, "revision": row.revision}


@router.put("/evidence/{record_id}")
def update_evidence(
    record_id: str,
    body: EvidenceIn,
    expected_revision: int = Query(ge=1),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = record_for(
        db, user, "evidence", record_id, body.org_id, body.site_id, write=True
    )
    guard_revision(row, expected_revision)
    if reason := lock_reason(db, "evidence", row):
        raise HTTPException(409, reason)
    contract = contract_for(
        db, user, body.contract_id, body.org_id, body.site_id, *ROLES["evidence"]
    )
    if body.unit != "hour":
        raise HTTPException(422, "Only hour units are supported")
    row.contract_id, row.contractor_id = contract.id, contract.contractor_id
    for name in ("work_code", "work_reference", "quantity", "unit"):
        setattr(row, name, getattr(body, name))
    row.service_date = utc(body.service_date)
    row.revision += 1
    audit(db, user, row, "evidence.updated", body.model_dump())
    db.commit()
    return {"id": row.id, "revision": row.revision}


@router.put("/invoices/{record_id}")
def update_invoice(
    record_id: str,
    body: InvoiceIn,
    expected_revision: int = Query(ge=1),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = record_for(
        db, user, "invoices", record_id, body.org_id, body.site_id, write=True
    )
    guard_revision(row, expected_revision)
    if reason := lock_reason(db, "invoices", row):
        raise HTTPException(409, reason)
    contract = contract_for(
        db, user, body.contract_id, body.org_id, body.site_id, *ROLES["invoices"]
    )
    if (
        db.query(Invoice)
        .filter(
            Invoice.org_id == row.org_id,
            Invoice.contractor_id == contract.contractor_id,
            Invoice.supplier_invoice_no == body.supplier_invoice_no,
            Invoice.id != row.id,
        )
        .first()
    ):
        raise HTTPException(409, "Supplier invoice reference already exists")
    if any(line.unit != "hour" for line in body.lines):
        raise HTTPException(422, "Only hour units are supported")
    row.contract_id, row.contractor_id = contract.id, contract.contractor_id
    row.supplier_invoice_no = body.supplier_invoice_no
    row.fingerprint = hashlib.sha256(
        json.dumps(body.model_dump(mode="json"), sort_keys=True).encode()
    ).hexdigest()
    db.query(InvoiceLine).filter_by(invoice_id=row.id).delete(synchronize_session=False)
    for number, line in enumerate(body.lines, 1):
        db.add(
            InvoiceLine(
                invoice_id=row.id,
                line_no=number,
                **line.model_dump(exclude={"service_date"}),
                service_date=utc(line.service_date),
                amount=(line.quantity * line.unit_price).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                ),
            )
        )
    row.revision += 1
    audit(
        db,
        user,
        row,
        "invoice.updated",
        {
            "revision": row.revision,
            "lines": len(body.lines),
            "contract_id": row.contract_id,
        },
    )
    db.commit()
    return {"id": row.id, "revision": row.revision}


@router.delete("/records/{kind}/{record_id}")
def delete_record(
    kind: str,
    record_id: str,
    org_id: str,
    site_id: str,
    expected_revision: int = Query(ge=1),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = record_for(db, user, kind, record_id, org_id, site_id, write=True)
    guard_revision(row, expected_revision)
    if reason := lock_reason(db, kind, row):
        raise HTTPException(409, reason)
    if kind == "contractors" and (
        db.query(Contract).filter_by(contractor_id=row.id).first()
        or db.query(Invoice).filter_by(contractor_id=row.id).first()
        or db.query(WorkRecord).filter_by(contractor_id=row.id).first()
    ):
        raise HTTPException(
            409,
            "Supplier has associated contracts, invoices or evidence; delete unused drafts first",
        )
    if kind == "contracts":
        if (
            db.query(ContractVersion)
            .filter_by(contract_id=row.id, status="approved")
            .first()
            or db.query(Invoice).filter_by(contract_id=row.id).first()
            or db.query(WorkRecord).filter_by(contract_id=row.id).first()
            or db.query(ContractVariation).filter_by(contract_id=row.id).first()
        ):
            raise HTTPException(
                409, "Contract has approved or associated records and must be retained"
            )
        for version in db.query(ContractVersion).filter_by(contract_id=row.id):
            db.query(RateLine).filter_by(contract_version_id=version.id).delete(
                synchronize_session=False
            )
            db.delete(version)
        db.flush()
    if kind == "invoices":
        db.query(InvoiceLine).filter_by(invoice_id=row.id).delete(
            synchronize_session=False
        )
    audit(db, user, row, kind.rstrip("s") + ".deleted", {"revision": row.revision})
    db.delete(row)
    db.commit()
    return {"id": record_id, "status": "deleted"}


def delete_endpoint(kind):
    def endpoint(
        record_id: str,
        org_id: str,
        site_id: str,
        expected_revision: int = Query(ge=1),
        user=Depends(get_current_user),
        db: Session = Depends(get_db),
    ):
        return delete_record(
            kind, record_id, org_id, site_id, expected_revision, user, db
        )

    return endpoint


def read_endpoint(kind):
    def endpoint(
        record_id: str,
        org_id: str,
        site_id: str,
        user=Depends(get_current_user),
        db: Session = Depends(get_db),
    ):
        return record_detail(kind, record_id, org_id, site_id, user, db)

    return endpoint


for resource in MODELS:
    router.add_api_route(
        f"/{resource}/{{record_id}}",
        delete_endpoint(resource),
        methods=["DELETE"],
        name="delete_" + resource,
    )
    if resource != "invoices":
        router.add_api_route(
            f"/{resource}/{{record_id}}",
            read_endpoint(resource),
            methods=["GET"],
            name="read_" + resource,
        )
