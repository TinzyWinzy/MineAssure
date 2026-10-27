"""Small UTF-8 CSV batches. Parsing is bounded and all-or-nothing.

Large asynchronous/XLSX uploads are intentionally outside the local pilot.
Original text, SHA256 and row errors are retained for authorized inspection.
"""

import csv
import hashlib
import io
import json

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.models import Contract, ImportBatch
from app.routers.domain import (
    EvidenceIn,
    InvoiceIn,
    LineIn,
    add_evidence,
    add_invoice,
    contract_for,
)
from app.services.access import audit, fields, scope

router = APIRouter(tags=["imports"])
MAX_BYTES = 256 * 1024
MAX_ROWS = 500


def batch_out(batch):
    metadata = json.loads(batch.errors_json or "{}")
    return {
        **fields(batch, "id", "kind", "filename", "sha256", "status", "created_at"),
        "errors": metadata.get("errors", []),
        "accepted": metadata.get("accepted", 0),
        "contract_id": metadata.get("contract_id"),
    }


@router.get("/imports")
def batches(
    org_id: str,
    site_id: str,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    scope(db, user, org_id, site_id)
    return [
        batch_out(b)
        for b in db.query(ImportBatch)
        .filter_by(org_id=org_id, site_id=site_id)
        .order_by(ImportBatch.created_at.desc())
        .limit(100)
    ]


@router.post("/imports/{kind}")
def import_csv(
    kind: str,
    org_id: str,
    site_id: str,
    contract_id: str,
    file: UploadFile,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if kind == "work":
        kind = "evidence"
    if kind not in ("evidence", "invoice"):
        raise HTTPException(422, "Supported CSV kinds are evidence and invoice")
    roles = (
        ("operations_verifier", "tenant_admin")
        if kind == "evidence"
        else ("ap_analyst", "tenant_admin")
    )
    contract_for(db, user, contract_id, org_id, site_id, *roles)
    # Serialize batches for one contract before checking the source hash.
    db.query(Contract).filter_by(id=contract_id).with_for_update().first()
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(422, "A UTF-8 .csv file is required")
    raw = file.file.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise HTTPException(413, "Pilot CSV limit is 256 KiB")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(422, "CSV must be UTF-8 text") from exc
    if "\x00" in text:
        raise HTTPException(422, "Binary content is not accepted")
    digest = hashlib.sha256(raw).hexdigest()
    for prior in (
        db.query(ImportBatch)
        .filter_by(org_id=org_id, site_id=site_id, kind=kind, sha256=digest)
        .all()
    ):
        if json.loads(prior.errors_json or "{}").get("contract_id") == contract_id:
            return batch_out(prior)
    batch = ImportBatch(
        org_id=org_id,
        site_id=site_id,
        kind=kind,
        filename=file.filename[:200],
        sha256=digest,
        source_text=text,
        created_by=user.id,
    )
    db.add(batch)
    db.flush()
    errors, parsed, accepted = [], [], 0
    reader = csv.DictReader(io.StringIO(text), strict=True)
    required = {"work_reference", "work_code", "quantity", "service_date", "unit"}
    if kind == "invoice":
        required |= {"supplier_invoice_no", "unit_price"}
    try:
        if (
            not reader.fieldnames
            or set(reader.fieldnames) != required
            or len(reader.fieldnames) != len(required)
        ):
            errors.append(
                {
                    "row": 1,
                    "message": "Headers must be exactly: " + ",".join(sorted(required)),
                }
            )
        else:
            for number, row in enumerate(reader, 2):
                if number > MAX_ROWS + 1:
                    errors.append(
                        {"row": number, "message": "Pilot CSV limit is 500 data rows"}
                    )
                    break
                try:
                    if None in row or any(value is None for value in row.values()):
                        raise ValueError("Column count differs from the header")
                    if kind == "evidence":
                        item = EvidenceIn(
                            org_id=org_id,
                            site_id=site_id,
                            contract_id=contract_id,
                            **row,
                        )
                    else:
                        reference = row.pop("supplier_invoice_no")
                        item = (reference, LineIn(**row))
                    parsed.append(item)
                except (ValidationError, ValueError) as exc:
                    errors.append({"row": number, "message": str(exc)[:1000]})
    except csv.Error as exc:
        errors.append({"row": reader.line_num, "message": "Malformed CSV: " + str(exc)})
    if not parsed and not errors:
        errors.append({"row": 2, "message": "CSV has no data rows"})
    if not errors:
        # Savepoint preserves a rejected staging record if any domain constraint fails.
        try:
            with db.begin_nested():
                if kind == "evidence":
                    for item in parsed:
                        record = add_evidence(db, user, item)
                        record.import_batch_id = batch.id
                        accepted += 1
                else:
                    grouped = {}
                    for reference, line in parsed:
                        grouped.setdefault(reference, []).append(line)
                    for reference, lines in grouped.items():
                        invoice = add_invoice(
                            db,
                            user,
                            InvoiceIn(
                                org_id=org_id,
                                site_id=site_id,
                                contract_id=contract_id,
                                supplier_invoice_no=reference,
                                lines=lines,
                            ),
                        )
                        invoice.import_batch_id = batch.id
                        accepted += len(lines)
        except HTTPException as exc:
            errors.append({"row": 0, "message": str(exc.detail)})
            accepted = 0
    batch.status = "rejected" if errors else "imported"
    batch.errors_json = json.dumps(
        {"contract_id": contract_id, "accepted": accepted, "errors": errors}
    )
    audit(
        db,
        user,
        batch,
        "import." + batch.status,
        {"sha256": digest, "accepted": accepted, "errors": len(errors)},
    )
    db.commit()
    return batch_out(batch)
