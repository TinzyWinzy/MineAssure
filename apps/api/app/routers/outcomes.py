"""Traceable mathematical outcomes and human-readable/machine-readable output."""

import json
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.models import (
    Approval,
    Contract,
    Contractor,
    ImportBatch,
    Invoice,
    ReconciliationRun,
    WorkRecord,
)
from app.routers.ingestion import csv_bytes
from app.routers.persistence import _run_out, _trusted
from app.services.access import entity_scope, fields

router = APIRouter(tags=["mathematical outcomes"])


def amount(value):
    return format(Decimal(value).quantize(Decimal("0.01")), "f")


def outcome_report(db, run):
    if not _trusted(run):
        raise HTTPException(
            409,
            "The run lacks trusted provenance and cannot produce a calculation report",
        )
    data = _run_out(db, run)
    invoice = db.get(Invoice, run.invoice_id)
    contract = db.get(Contract, invoice.contract_id)
    supplier = db.get(Contractor, invoice.contractor_id)
    snapshots = {
        row["invoice_line"]["id"]: row for row in data["input_snapshot"]["lines"]
    }
    columns = (
        "invoiced_amount",
        "supported_amount",
        "unverified_amount",
        "quantified_variance",
        "approved_amount",
    )
    totals = {column: Decimal(0) for column in columns}
    lines = []
    for result in data["results"]:
        snapshot = snapshots[result["invoice_line_id"]]
        source = snapshot["invoice_line"]
        terms = snapshot.get("contract")
        rate = (
            next(
                (r for r in terms["rates"] if r["work_code"] == source["work_code"]),
                None,
            )
            if terms
            else None
        )
        quantity, price = Decimal(source["quantity"]), Decimal(source["unit_price"])
        allocated = Decimal(snapshot["allocated_quantity"])
        eligible = min(quantity, allocated)
        if rate and rate.get("cap_hours") is not None:
            eligible = min(eligible, Decimal(rate["cap_hours"]))
        determined = Decimal(result["unverified_amount"]) == 0
        if not determined:
            eligible = Decimal(0)
        rate_value = Decimal(rate["rate"]) if rate else None
        steps = [
            {
                "label": "Invoiced",
                "formula": f"{quantity} hours × USD {price}/hour",
                "value": amount(result["invoiced_amount"]),
                "unit": "USD",
            },
            {
                "label": "Verified hours considered",
                "formula": "Independently attested hours considered in this frozen assessment",
                "value": str(allocated),
                "unit": "hours",
            },
            {
                "label": "Eligible hours",
                "formula": f"min(invoiced {quantity}, allocated {allocated}"
                + (
                    f", cap {rate['cap_hours']}"
                    if rate and rate.get("cap_hours") is not None
                    else ""
                )
                + ")",
                "value": str(eligible),
                "unit": "hours",
            },
            {
                "label": "Provisionally supported",
                "formula": f"min(invoiced, {eligible} hours × USD {rate_value}/hour)"
                if determined and rate
                else "Undetermined: approved terms and unique attested evidence are required",
                "value": amount(result["supported_amount"]),
                "unit": "USD",
            },
            {
                "label": "Quantified variance",
                "formula": "max(invoiced − provisionally supported, 0), counted once"
                if determined
                else "Undetermined; the amount is classified as unverified",
                "value": amount(result["quantified_variance"]),
                "unit": "USD",
            },
            {
                "label": "Unverified",
                "formula": "Invoiced amount requiring approved terms or resolved evidence"
                if not determined
                else "No unresolved source balance on this line",
                "value": amount(result["unverified_amount"]),
                "unit": "USD",
            },
            {
                "label": "Approved",
                "formula": "Distinct finance approver's immutable decision",
                "value": amount(result["approved_amount"]),
                "unit": "USD",
            },
        ]
        evidence = []
        for frozen in snapshot["evidence"]:
            work = db.get(WorkRecord, frozen["id"])
            batch = (
                db.get(ImportBatch, work.import_batch_id)
                if work and work.import_batch_id
                else None
            )
            evidence.append(
                {
                    **frozen,
                    "import_file": fields(batch, "id", "filename", "sha256")
                    if batch
                    else None,
                }
            )
        decision = (
            db.query(Approval)
            .filter_by(run_id=run.id, invoice_line_id=source["id"])
            .first()
        )
        for column in columns:
            totals[column] += Decimal(result[column])
        lines.append(
            {
                **result,
                "invoice_source": source,
                "contract_source": terms,
                "evidence_sources": evidence,
                "calculation_steps": steps,
                "variance_determined": determined,
                "eligible_unapproved": amount(
                    max(
                        Decimal(0),
                        Decimal(result["supported_amount"])
                        - Decimal(result["approved_amount"]),
                    )
                ),
                "decision_source": fields(
                    decision,
                    "id",
                    "approver_id",
                    "decision",
                    "amount",
                    "reason",
                    "created_at",
                )
                if decision
                else None,
                "conservation_valid": Decimal(result["invoiced_amount"])
                == sum(
                    (
                        Decimal(result[k])
                        for k in (
                            "supported_amount",
                            "unverified_amount",
                            "quantified_variance",
                        )
                    ),
                    Decimal(0),
                ),
            }
        )
    source_file = (
        db.get(ImportBatch, invoice.import_batch_id)
        if invoice.import_batch_id
        else None
    )
    return {
        "run_id": run.id,
        "invoice_id": invoice.id,
        "invoice_reference": invoice.supplier_invoice_no,
        "contract": fields(contract, "id", "title") if contract else None,
        "contractor": fields(supplier, "id", "name") if supplier else None,
        "source_file": fields(source_file, "id", "filename", "sha256")
        if source_file
        else None,
        "currency": invoice.currency,
        "rule_set_version": run.rule_set_version,
        "input_hash": run.input_hash,
        "is_current": run.is_current,
        "totals": {key: amount(value) for key, value in totals.items()},
        "conservation_formula": "Invoiced = provisionally supported + unverified + quantified variance. Approved is a subset of supported.",
        "lines": lines,
    }


@router.get("/reconciliation/runs/{run_id}/outcomes")
def outcomes(
    run_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)
):
    return outcome_report(db, entity_scope(db, user, db.get(ReconciliationRun, run_id)))


@router.get("/reconciliation/runs/{run_id}/report")
def download_report(
    run_id: str,
    format: Literal["json", "csv"] = "csv",
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    report = outcome_report(
        db, entity_scope(db, user, db.get(ReconciliationRun, run_id))
    )
    if format == "json":
        content, mime = json.dumps(report, indent=2).encode(), "application/json"
    else:
        headers = [
            "invoice_reference",
            "invoice_line_id",
            "work_reference",
            "invoiced_amount",
            "supported_amount",
            "unverified_amount",
            "quantified_variance",
            "variance_determined",
            "approved_amount",
            "eligible_unapproved",
            "currency",
            "run_id",
            "input_hash",
        ]
        rows = [
            [
                report["invoice_reference"],
                row["invoice_line_id"],
                row["invoice_source"].get("work_reference", ""),
                row["invoiced_amount"],
                row["supported_amount"],
                row["unverified_amount"],
                row["quantified_variance"],
                row["variance_determined"],
                row["approved_amount"],
                row["eligible_unapproved"],
                report["currency"],
                run_id,
                report["input_hash"],
            ]
            for row in report["lines"]
        ]
        content, mime = csv_bytes(headers, rows), "text/csv"
    return Response(
        content,
        media_type=mime,
        headers={
            "Content-Disposition": f'attachment; filename="reconciliation-{run_id}.{format}"'
        },
    )
