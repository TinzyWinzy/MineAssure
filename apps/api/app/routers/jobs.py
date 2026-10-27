"""Scoped asynchronous reconciliation with durable input identity."""

import hashlib
import json
from datetime import UTC
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.models import Invoice, InvoiceLine, JobRun
from app.routers.domain import Scoped, Text
from app.services.access import audit, entity_scope, fields, scope

router = APIRouter(tags=["jobs"])


class ReconciliationJobIn(Scoped):
    invoice_id: Text
    idempotency_key: Text


def invoice_hash(db, invoice):
    data = {
        "invoice": fields(invoice, "id", "contract_id", "currency", "created_by"),
        "lines": [
            fields(
                line,
                "id",
                "line_no",
                "quantity",
                "unit_price",
                "amount",
                "service_date",
                "work_code",
                "work_reference",
                "unit",
            )
            for line in db.query(InvoiceLine)
            .filter_by(invoice_id=invoice.id)
            .order_by(InvoiceLine.line_no)
        ],
    }
    # ORM-created values and database round-trips can differ in numeric scale
    # and timezone representation while expressing the same immutable input.
    for line in data["lines"]:
        for name in ("quantity", "unit_price", "amount"):
            line[name] = format(Decimal(line[name]).quantize(Decimal("0.000001")), "f")
        if line["service_date"]:
            from datetime import datetime

            date = datetime.fromisoformat(line["service_date"])
            line["service_date"] = (
                date.replace(tzinfo=UTC).isoformat()
                if date.tzinfo is None
                else date.astimezone(UTC).isoformat()
            )
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


def job_out(job):
    return {
        **fields(job, "id", "kind", "status", "attempts", "created_at", "completed_at"),
        "result": json.loads(job.result) if job.result and job.org_id else None,
    }


@router.post("/jobs/reconciliation", status_code=202)
def enqueue_reconciliation(
    body: ReconciliationJobIn,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    scope(db, user, body.org_id, body.site_id, "ap_analyst")
    invoice = db.query(Invoice).filter_by(id=body.invoice_id).with_for_update().first()
    if not invoice or (invoice.org_id, invoice.site_id) != (body.org_id, body.site_id):
        raise HTTPException(404, "Invoice not found")
    prior = (
        db.query(JobRun)
        .filter_by(
            org_id=body.org_id,
            site_id=body.site_id,
            kind="reconciliation",
            idempotency_key=body.idempotency_key,
        )
        .first()
    )
    if prior:
        if json.loads(prior.payload)["invoice_id"] != invoice.id:
            raise HTTPException(
                409, "Idempotency key already belongs to another invoice"
            )
        return job_out(prior)
    # Different request keys for a still-pending invoice share the active job.
    active = (
        db.query(JobRun)
        .filter(
            JobRun.org_id == body.org_id,
            JobRun.site_id == body.site_id,
            JobRun.kind == "reconciliation",
            JobRun.status.in_(["queued", "running"]),
        )
        .all()
    )
    for job in active:
        if json.loads(job.payload)["invoice_id"] == invoice.id:
            return job_out(job)
    job = JobRun(
        org_id=body.org_id,
        site_id=body.site_id,
        created_by=user.id,
        kind="reconciliation",
        idempotency_key=body.idempotency_key,
        payload=json.dumps(
            {"invoice_id": invoice.id, "invoice_hash": invoice_hash(db, invoice)}
        ),
    )
    db.add(job)
    db.flush()
    audit(db, user, job, "job.queued", {"invoice_id": invoice.id})
    db.commit()
    return job_out(job)


@router.get("/jobs/{job_id}")
def get_job(job_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    job = db.get(JobRun, job_id)
    if job and not job.org_id:
        raise HTTPException(404, "Job not found")
    return job_out(entity_scope(db, user, job))
