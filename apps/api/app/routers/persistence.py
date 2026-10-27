"""Transactional persisted reconciliation, review and approved-only exports."""

import csv
import hashlib
import io
import json
from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import Field
from sqlalchemy.orm import Session

from app.attestation import attestation_hash
from app.auth import get_current_user
from app.crypto_sign import sign_payload
from app.db import get_db
from app.engine import (
    ContractVersionInput,
    InvoiceLineInput,
    reconcile_line,
    select_contract_version,
)
from app.models import (
    Approval,
    AuditEvent,
    Case,
    CaseComment,
    ContractVersion,
    EvidenceAllocation,
    ExportBatch,
    ExportLine,
    Finding,
    Invoice,
    InvoiceLine,
    RateLine,
    ReconciliationLineResult,
    ReconciliationRun,
    WorkRecord,
)
from app.routers.domain import Scoped, StrictModel, Text, invoice_row, utc
from app.services.access import audit, entity_scope, fields, scope
from app.services.allocation import allocated_quantity, reserve_allocation
from app.services.signing import get_or_create_user_key

router = APIRouter(tags=["assurance"])


class CreateRunIn(Scoped):
    invoice_id: Text
    idempotency_key: Text | None = None


class ApprovalIn(StrictModel):
    run_id: Text
    invoice_line_id: Text
    decision: Literal["approved", "rejected"]
    amount: Decimal = Field(
        ge=0,
        le=Decimal(100000000),
        max_digits=18,
        decimal_places=2,
        allow_inf_nan=False,
    )
    reason: str = Field(min_length=3, max_length=2000)
    run_version: int = Field(ge=1)
    client_signature: str | None = None
    client_public_key_spki: str | None = None


class ExportIn(Scoped):
    run_id: Text
    idempotency_key: Text | None = None


def _hash(payload):
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str, separators=(",", ":")).encode()
    ).hexdigest()


def _trusted(run):
    if not run or not run.created_by or not run.input_snapshot:
        return False
    try:
        return _hash(json.loads(run.input_snapshot)) == run.input_hash
    except (ValueError, TypeError):
        return False


def _contract_input(db, cv):
    return ContractVersionInput(
        id=cv.id,
        status=cv.status,
        effective_from=utc(cv.effective_from),
        effective_to=utc(cv.effective_to),
        currency=cv.currency,
        rate_lines=[
            fields(r, "work_code", "unit", "rate", "cap_hours")
            for r in db.query(RateLine)
            .filter_by(contract_version_id=cv.id)
            .order_by(RateLine.id)
        ],
    )


def _run_out(db, run):
    results = []
    for row in (
        db.query(ReconciliationLineResult)
        .filter_by(run_id=run.id)
        .order_by(ReconciliationLineResult.invoice_line_id)
    ):
        decision = (
            db.query(Approval)
            .filter_by(run_id=run.id, invoice_line_id=row.invoice_line_id)
            .first()
        )
        results.append(
            {
                **fields(
                    row,
                    "id",
                    "invoice_line_id",
                    "invoiced_amount",
                    "supported_amount",
                    "unverified_amount",
                    "quantified_variance",
                    "explanation",
                    "evidence_refs",
                ),
                "approved_amount": str(decision.amount)
                if decision and decision.decision == "approved"
                else "0.00",
                "decision": decision.decision if decision else None,
                "findings": [
                    fields(
                        f, "id", "rule_code", "severity", "message", "quantified_amount"
                    )
                    for f in db.query(Finding)
                    .filter_by(run_id=run.id, invoice_line_id=row.invoice_line_id)
                    .order_by(Finding.rule_code)
                ],
            }
        )
    output = {
        **fields(
            run,
            "id",
            "invoice_id",
            "is_current",
            "status",
            "version",
            "created_by",
            "input_hash",
            "rule_set_version",
            "completed_at",
        ),
        "results": results,
        "input_snapshot": json.loads(run.input_snapshot) if _trusted(run) else None,
        "legacy_quarantined": not _trusted(run),
    }
    if not _trusted(run):
        output.update(status="legacy_quarantined", is_current=False)
        for row in output["results"]:
            row["approved_amount"] = "0.00"
    return output


@router.post("/reconciliation/runs")
def create_run(
    body: CreateRunIn, user=Depends(get_current_user), db: Session = Depends(get_db)
):
    return reconcile_invoice(body, user, db)


def reconcile_invoice(body, user, db, *, commit=True):
    scope(db, user, body.org_id, body.site_id, "ap_analyst")
    invoice = db.query(Invoice).filter_by(id=body.invoice_id).with_for_update().first()
    if not invoice or (invoice.org_id, invoice.site_id) != (body.org_id, body.site_id):
        raise HTTPException(404, "Invoice not found")
    if body.idempotency_key:
        existing = (
            db.query(ReconciliationRun)
            .filter_by(invoice_id=invoice.id, idempotency_key=body.idempotency_key)
            .first()
        )
        if existing:
            return _run_out(db, existing)
    prior = (
        db.query(ReconciliationRun)
        .filter_by(invoice_id=invoice.id, is_current=True)
        .all()
    )
    for old in prior:
        if db.query(Approval).filter_by(run_id=old.id).first():
            raise HTTPException(
                409,
                "A decided invoice cannot be rerun; explicit audited reversal is required",
            )
        old.is_current = False
        for allocation in db.query(EvidenceAllocation).filter_by(
            reconciliation_run_id=old.id, status="reserved"
        ):
            allocation.status, allocation.released_at = "released", datetime.now(UTC)
        audit(db, user, old, "run.superseded")
    db.flush()
    versions = [
        _contract_input(db, cv)
        for cv in db.query(ContractVersion)
        .filter_by(contract_id=invoice.contract_id)
        .all()
    ]
    run = ReconciliationRun(
        org_id=invoice.org_id,
        site_id=invoice.site_id,
        invoice_id=invoice.id,
        created_by=user.id,
        idempotency_key=body.idempotency_key,
        status="running",
        version=1,
        rule_set_version="pilot-1.1",
    )
    db.add(run)
    db.flush()
    lines = (
        db.query(InvoiceLine)
        .filter_by(invoice_id=invoice.id)
        .order_by(InvoiceLine.line_no)
        .all()
    )
    if not lines:
        raise HTTPException(409, "Invoice has no lines")
    snapshots = []
    for line in lines:
        cv = (
            select_contract_version(versions, utc(line.service_date))
            if line.service_date
            else None
        )
        matching = []
        if line.work_reference and line.service_date is not None:
            matching = (
                db.query(WorkRecord)
                .filter_by(
                    org_id=invoice.org_id,
                    site_id=invoice.site_id,
                    contract_id=invoice.contract_id,
                    work_reference=line.work_reference,
                    work_code=line.work_code,
                    unit=line.unit,
                    status="attested",
                )
                .order_by(WorkRecord.id)
                .with_for_update()
                .all()
            )
            matching = [
                w
                for w in matching
                if utc(w.service_date).date() == utc(line.service_date).date()
            ]
        qty, conflict, ambiguous = Decimal(0), False, len(matching) > 1
        refs = []
        if len(matching) == 1:
            work = matching[0]
            used = allocated_quantity(db, work.id)
            remaining = work.quantity - used
            if remaining <= 0 or (used > 0 and line.quantity > remaining):
                conflict = True
            else:
                qty = min(line.quantity, remaining)
                reserve_allocation(db, work.id, line.id, run.id, qty)
                refs = [work.id]
        duplicate_line = bool(
            line.work_reference
            and sum(1 for other in lines if other.work_reference == line.work_reference)
            > 1
        )
        out_of_contract = cv is None and any(v.status == "approved" for v in versions)
        result = reconcile_line(
            InvoiceLineInput(
                line.id,
                line.quantity,
                line.unit,
                line.unit_price,
                utc(line.service_date),
                line.work_code,
                line.work_reference,
            ),
            cv if invoice.currency == "USD" else None,
            qty,
            refs,
            duplicate_invoice=False,
            duplicate_work_ref=conflict or duplicate_line,
            service_out_of_contract=out_of_contract,
        )
        if ambiguous:
            result.findings.append(
                {
                    "rule_code": "R005",
                    "severity": "high",
                    "message": "Multiple attested records match; evidence is ambiguous and amount remains unverified.",
                }
            )
        if conflict:
            result.findings.append(
                {
                    "rule_code": "R005",
                    "severity": "high",
                    "message": "Evidence allocation conflict: verified quantity is reserved or consumed by another invoice.",
                }
            )
        if result.supported_amount <= 0:
            for allocation in db.query(EvidenceAllocation).filter_by(
                reconciliation_run_id=run.id, invoice_line_id=line.id
            ):
                allocation.status, allocation.released_at = (
                    "released",
                    datetime.now(UTC),
                )
        db.add(
            ReconciliationLineResult(
                run_id=run.id,
                invoice_line_id=line.id,
                invoiced_amount=result.invoiced_amount,
                supported_amount=result.supported_amount,
                unverified_amount=result.unverified_amount,
                quantified_variance=result.quantified_variance,
                approved_amount=0,
                explanation=result.explanation,
                evidence_refs=",".join(refs),
            )
        )
        for detail in result.findings:
            finding = Finding(run_id=run.id, invoice_line_id=line.id, **detail)
            db.add(finding)
            db.flush()
            db.add(
                Case(
                    org_id=invoice.org_id,
                    site_id=invoice.site_id,
                    finding_id=finding.id,
                )
            )
        snapshots.append(
            {
                "invoice_line": fields(
                    line,
                    "id",
                    "quantity",
                    "unit",
                    "unit_price",
                    "service_date",
                    "work_code",
                    "work_reference",
                ),
                "contract": {
                    "id": cv.id,
                    "effective_from": str(cv.effective_from),
                    "effective_to": str(cv.effective_to),
                    "currency": cv.currency,
                    "rates": cv.rate_lines,
                }
                if cv
                else None,
                "evidence": [
                    fields(
                        w,
                        "id",
                        "quantity",
                        "status",
                        "attested_by",
                        "attested_at",
                        "service_date",
                        "work_reference",
                    )
                    for w in matching
                ],
                "allocated_quantity": str(qty),
                "allocation_conflict": conflict,
                "duplicate_line": duplicate_line,
            }
        )
    snapshot = {
        "rule_set_version": run.rule_set_version,
        "invoice_id": invoice.id,
        "currency": invoice.currency,
        "lines": snapshots,
    }
    run.input_snapshot = json.dumps(snapshot, sort_keys=True, default=str)
    run.input_hash, run.status, run.completed_at = (
        _hash(snapshot),
        "completed",
        datetime.now(UTC),
    )
    invoice.status = "reconciled"
    audit(
        db,
        user,
        run,
        "run.completed",
        {"input_hash": run.input_hash, "lines": len(lines)},
    )
    if commit:
        db.commit()
    else:
        db.flush()
    return _run_out(db, run)


@router.get("/reconciliation/runs/{run_id}")
def get_run(run_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return _run_out(db, entity_scope(db, user, db.get(ReconciliationRun, run_id)))


@router.post("/approvals")
def create_approval(
    body: ApprovalIn, user=Depends(get_current_user), db: Session = Depends(get_db)
):
    run = entity_scope(
        db,
        user,
        db.query(ReconciliationRun).filter_by(id=body.run_id).with_for_update().first(),
        "finance_approver",
    )
    invoice = db.get(Invoice, run.invoice_id)
    if not _trusted(run) or not invoice.created_by:
        raise HTTPException(
            409,
            "Legacy or incomplete provenance is quarantined; a new controlled invoice is required",
        )
    if db.query(ExportBatch).filter_by(run_id=run.id).first():
        raise HTTPException(
            409,
            "Export finalized this run; further decisions require an audited reversal",
        )
    if (
        not run.is_current
        or run.status != "completed"
        or run.version != body.run_version
    ):
        raise HTTPException(409, "Stale run or review version; refresh before deciding")
    if (
        user.id in (run.created_by, invoice.created_by)
        or db.query(AuditEvent)
        .filter_by(entity_id=invoice.id, actor_id=user.id, action="invoice.updated")
        .first()
    ):
        raise HTTPException(
            403, "Separation of duties: preparer cannot approve their own invoice/run"
        )
    result = (
        db.query(ReconciliationLineResult)
        .filter_by(run_id=run.id, invoice_line_id=body.invoice_line_id)
        .first()
    )
    if not result:
        raise HTTPException(404, "Line result not found")
    if (
        db.query(Approval)
        .filter_by(run_id=run.id, invoice_line_id=body.invoice_line_id)
        .first()
    ):
        raise HTTPException(409, "Line already has an immutable decision")
    if body.decision == "approved":
        if (
            body.amount <= 0
            or body.amount > result.supported_amount
            or result.unverified_amount > 0
        ):
            raise HTTPException(
                422, "Only positive, determined supported amounts may be approved"
            )
        if body.amount > Decimal(50000):
            raise HTTPException(403, "Pilot finance authority is USD 50,000 per line")
    elif body.amount != 0:
        raise HTTPException(422, "Rejected decisions must have amount zero")
    approval_payload = {
        "run_id": run.id,
        "invoice_line_id": body.invoice_line_id,
        "approver_id": user.id,
        "decision": body.decision,
        "amount": str(body.amount),
        "reason": body.reason,
        "version": run.version,
    }
    payload_hash = attestation_hash(approval_payload)
    full_hash = attestation_hash(
        {**approval_payload, "created_at": datetime.now(UTC).isoformat()}
    )
    client_sig = None
    signer_key_id = None
    if body.client_signature and body.client_public_key_spki:
        from app.crypto_sign import verify_webcrypto_signature

        client_msg = json.dumps(
            {
                "run_id": run.id,
                "invoice_line_id": body.invoice_line_id,
                "decision": body.decision,
                "amount": str(body.amount),
                "reason": body.reason,
                "run_version": run.version,
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        if not verify_webcrypto_signature(
            body.client_public_key_spki, client_msg, body.client_signature
        ):
            raise HTTPException(403, "Invalid client signature")
        client_sig = body.client_signature
        # register the public key if not already
        from app.models import UserPublicKey

        if (
            not db.query(UserPublicKey)
            .filter_by(user_id=user.id, spki_b64=body.client_public_key_spki)
            .first()
        ):
            db.add(UserPublicKey(user_id=user.id, spki_b64=body.client_public_key_spki))
            db.flush()
    else:
        signer_key = get_or_create_user_key(db, user.id)
        client_sig = sign_payload(signer_key.encrypted_private_key, payload_hash)
        signer_key_id = signer_key.id
    approval = Approval(
        run_id=run.id,
        invoice_line_id=body.invoice_line_id,
        approver_id=user.id,
        decision=body.decision,
        amount=body.amount,
        reason=body.reason,
        version=run.version,
        attestation_hash=full_hash,
        signature=client_sig,
        signer_key_id=signer_key_id,
    )
    db.add(approval)
    run.version += 1
    for allocation in db.query(EvidenceAllocation).filter_by(
        reconciliation_run_id=run.id,
        invoice_line_id=body.invoice_line_id,
        status="reserved",
    ):
        allocation.status = "consumed" if body.decision == "approved" else "released"
        if allocation.status == "released":
            allocation.released_at = datetime.now(UTC)
    invoice.status = "partially_approved" if body.decision == "approved" else "reviewed"
    db.flush()
    audit(
        db,
        user,
        run,
        "line." + body.decision,
        {
            "approval_id": approval.id,
            "line_id": body.invoice_line_id,
            "amount": str(body.amount),
            "reason": body.reason,
            "version": body.run_version,
        },
    )
    db.commit()
    return {
        "id": approval.id,
        "decision": approval.decision,
        "amount": str(approval.amount),
        "run_version": run.version,
    }


@router.get("/approvals")
def approvals(
    org_id: str,
    site_id: str,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    scope(db, user, org_id, site_id)
    rows = (
        db.query(Approval)
        .join(ReconciliationRun, Approval.run_id == ReconciliationRun.id)
        .filter(
            ReconciliationRun.org_id == org_id, ReconciliationRun.site_id == site_id
        )
        .order_by(Approval.created_at.desc())
        .limit(200)
    )
    return [
        fields(
            a,
            "id",
            "run_id",
            "invoice_line_id",
            "approver_id",
            "decision",
            "amount",
            "reason",
            "created_at",
        )
        for a in rows
    ]


def _export_out(db, batch):
    lines = (
        db.query(ExportLine)
        .filter_by(export_batch_id=batch.id)
        .order_by(ExportLine.invoice_line_id)
        .all()
    )
    return {
        **fields(batch, "id", "status", "run_id", "artifact_hash", "created_at"),
        "total_minor": sum(line.amount_minor for line in lines),
        "line_count": len(lines),
        "download_url": f"/api/v1/exports/{batch.id}/download",
    }


def csv_safe(value):
    text = str(value or "")
    return "'" + text if text.startswith(("=", "+", "-", "@", "\t", "\r")) else text


@router.post("/exports")
def create_export(
    body: ExportIn, user=Depends(get_current_user), db: Session = Depends(get_db)
):
    scope(db, user, body.org_id, body.site_id, "finance_approver")
    run = (
        db.query(ReconciliationRun).filter_by(id=body.run_id).with_for_update().first()
    )
    if not run or (run.org_id, run.site_id) != (body.org_id, body.site_id):
        raise HTTPException(404, "Run not found")
    if not _trusted(run) or not db.get(Invoice, run.invoice_id).created_by:
        raise HTTPException(409, "Legacy or incomplete provenance cannot be exported")
    if not run.is_current:
        raise HTTPException(409, "Cannot export a stale run")
    if body.idempotency_key:
        keyed = (
            db.query(ExportBatch)
            .filter_by(
                org_id=body.org_id,
                site_id=body.site_id,
                idempotency_key=body.idempotency_key,
            )
            .first()
        )
        if keyed:
            if keyed.run_id != run.id:
                raise HTTPException(
                    409, "Idempotency key was already used for a different run"
                )
            return _export_out(db, keyed)
    existing = db.query(ExportBatch).filter_by(run_id=run.id).first()
    if existing:
        return _export_out(db, existing)
    approved = (
        db.query(Approval)
        .filter_by(run_id=run.id, decision="approved")
        .order_by(Approval.invoice_line_id)
        .all()
    )
    if not approved:
        raise HTTPException(409, "No approved costs to export")
    batch = ExportBatch(
        org_id=run.org_id,
        site_id=run.site_id,
        run_id=run.id,
        created_by=user.id,
        idempotency_key=body.idempotency_key,
        status="created",
        attestation_hash=attestation_hash(
            {
                "run_id": run.id,
                "org_id": run.org_id,
                "site_id": run.site_id,
                "created_by": user.id,
                "input_hash": run.input_hash,
                "approved_ids": [a.id for a in approved],
            }
        ),
    )
    db.add(batch)
    db.flush()
    invoice = db.get(Invoice, run.invoice_id)
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(
        [
            "batch_id",
            "organisation",
            "site",
            "contractor",
            "invoice",
            "line",
            "work_code",
            "service_date",
            "currency",
            "amount_minor",
            "run_id",
            "approval_id",
            "input_hash",
        ]
    )
    for decision in approved:
        line = db.get(InvoiceLine, decision.invoice_line_id)
        minor = int(decision.amount * 100)
        db.add(
            ExportLine(
                export_batch_id=batch.id,
                invoice_line_id=line.id,
                approval_id=decision.id,
                amount_minor=minor,
                currency="USD",
                provenance=f"run={run.id};approval={decision.id};input_hash={run.input_hash}",
            )
        )
        writer.writerow(
            [
                csv_safe(v)
                for v in [
                    batch.id,
                    run.org_id,
                    run.site_id,
                    invoice.contractor_id,
                    invoice.supplier_invoice_no,
                    line.line_no,
                    line.work_code,
                    line.service_date.date().isoformat(),
                    "USD",
                    minor,
                    run.id,
                    decision.id,
                    run.input_hash,
                ]
            ]
        )
    batch.artifact_text = stream.getvalue()
    batch.artifact_hash = hashlib.sha256(batch.artifact_text.encode()).hexdigest()
    audit(
        db,
        user,
        batch,
        "export.created",
        {"hash": batch.artifact_hash, "approved_lines": len(approved)},
    )
    db.commit()
    return _export_out(db, batch)


@router.get("/exports")
def exports(
    org_id: str,
    site_id: str,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    scope(db, user, org_id, site_id, "finance_approver", "auditor", "tenant_admin")
    return [
        _export_out(db, b)
        for b in db.query(ExportBatch)
        .filter_by(org_id=org_id, site_id=site_id)
        .order_by(ExportBatch.created_at.desc())
        .limit(200)
    ]


@router.get("/exports/{batch_id}/download")
def download(
    batch_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)
):
    batch = entity_scope(
        db,
        user,
        db.get(ExportBatch, batch_id),
        "finance_approver",
        "auditor",
        "tenant_admin",
    )
    if (
        not batch.artifact_text
        or hashlib.sha256(batch.artifact_text.encode()).hexdigest()
        != batch.artifact_hash
    ):
        raise HTTPException(409, "Legacy or invalid export artifact is quarantined")
    return Response(
        batch.artifact_text or "",
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="mineassure-{batch.id}.csv"',
            "X-Artifact-SHA256": batch.artifact_hash or "",
        },
    )


class CreateCaseIn(Scoped):
    finding_id: Text
    assignee_id: Text | None = None


class CommentIn(StrictModel):
    body: str = Field(min_length=1, max_length=4000)


@router.post("/cases")
def create_case(
    body: CreateCaseIn, user=Depends(get_current_user), db: Session = Depends(get_db)
):
    scope(db, user, body.org_id, body.site_id, "ap_analyst", "finance_approver")
    finding = db.get(Finding, body.finding_id)
    run = db.get(ReconciliationRun, finding.run_id) if finding else None
    if not run or (run.org_id, run.site_id) != (body.org_id, body.site_id):
        raise HTTPException(404, "Finding not found")
    if body.assignee_id:
        raise HTTPException(
            422,
            "Assignment requires a reviewed site membership workflow; leave unassigned",
        )
    case = Case(org_id=body.org_id, site_id=body.site_id, finding_id=finding.id)
    db.add(case)
    db.flush()
    audit(db, user, case, "case.opened")
    db.commit()
    return fields(case, "id", "status", "assignee_id")


@router.get("/cases")
def cases(
    org_id: str,
    site_id: str,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    scope(db, user, org_id, site_id)
    out = []
    for case in (
        db.query(Case)
        .filter_by(org_id=org_id, site_id=site_id)
        .order_by(Case.created_at.desc())
        .limit(200)
    ):
        finding = db.get(Finding, case.finding_id)
        run = db.get(ReconciliationRun, finding.run_id) if finding else None
        if run and not run.is_current:
            continue
        out.append(
            {
                **fields(
                    case, "id", "status", "assignee_id", "finding_id", "created_at"
                ),
                "rule_code": finding.rule_code if finding else None,
                "rule": finding.rule_code if finding else None,
                "message": finding.message if finding else "Investigation",
                "invoice_id": run.invoice_id if run else None,
                "comments": [
                    fields(c, "id", "body", "author_id", "created_at")
                    for c in db.query(CaseComment)
                    .filter_by(case_id=case.id)
                    .order_by(CaseComment.created_at)
                ],
            }
        )
    return out


@router.post("/cases/{case_id}/comments")
def add_comment(
    case_id: str,
    body: CommentIn,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    case = entity_scope(
        db, user, db.get(Case, case_id), "ap_analyst", "finance_approver"
    )
    comment = CaseComment(case_id=case.id, author_id=user.id, body=body.body)
    db.add(comment)
    audit(db, user, case, "case.commented", {"body": body.body})
    db.commit()
    return fields(comment, "id", "body", "author_id", "created_at")


@router.get("/audit")
def audit_history(
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
            e,
            "id",
            "actor_id",
            "action",
            "entity_type",
            "entity_id",
            "new_value",
            "request_id",
            "created_at",
        )
        for e in db.query(AuditEvent)
        .filter_by(org_id=org_id, site_id=site_id)
        .order_by(AuditEvent.created_at.desc(), AuditEvent.id)
        .offset(offset)
        .limit(limit)
    ]


@router.get("/dashboard")
def dashboard(
    org_id: str,
    site_id: str,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    scope(db, user, org_id, site_id)
    totals = {
        name: Decimal(0)
        for name in (
            "invoiced_amount",
            "supported_amount",
            "unverified_amount",
            "quantified_variance",
            "approved_amount",
        )
    }
    invoices = db.query(Invoice).filter_by(org_id=org_id, site_id=site_id).all()
    for invoice in invoices:
        invoice_lines = db.query(InvoiceLine).filter_by(invoice_id=invoice.id).all()
        totals["invoiced_amount"] += sum(
            (line.amount for line in invoice_lines), Decimal(0)
        )
        run = (
            db.query(ReconciliationRun)
            .filter_by(invoice_id=invoice.id, is_current=True)
            .first()
        )
        if _trusted(run):
            for result in db.query(ReconciliationLineResult).filter_by(run_id=run.id):
                totals["supported_amount"] += result.supported_amount
                totals["unverified_amount"] += result.unverified_amount
                totals["quantified_variance"] += result.quantified_variance
            totals["approved_amount"] += sum(
                (
                    a.amount
                    for a in db.query(Approval).filter_by(
                        run_id=run.id, decision="approved"
                    )
                ),
                Decimal(0),
            )
        else:
            totals["unverified_amount"] += sum(
                (line.amount for line in invoice_lines), Decimal(0)
            )
    return {
        "totals": {k: str(v.quantize(Decimal("0.01"))) for k, v in totals.items()},
        "invoice_count": len(invoices),
        "invoices": [invoice_row(db, i) for i in invoices[:8]],
        "recent_audit": audit_history(org_id, site_id, 8, 0, user, db),
        "open_disputes": db.query(Case)
        .filter_by(org_id=org_id, site_id=site_id, status="open")
        .count(),
    }
