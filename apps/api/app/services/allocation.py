"""Evidence allocation ledger with concurrency safety."""

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import EvidenceAllocation, EvidenceFile, WorkRecord


def allocated_quantity(db: Session, work_record_id: str) -> Decimal:
    rows = (
        db.query(EvidenceAllocation)
        .filter(
            EvidenceAllocation.work_record_id == work_record_id,
            EvidenceAllocation.status.in_(["reserved", "consumed"]),
        )
        .all()
    )
    return sum((r.quantity for r in rows), Decimal(0))


def reserve_allocation(
    db: Session,
    work_record_id: str,
    invoice_line_id: str,
    run_id: str | None,
    qty: Decimal,
) -> EvidenceAllocation:
    if not qty.is_finite() or qty <= 0:
        raise ValueError("allocation quantity must be finite and positive")
    # Row lock on work record to serialize concurrent allocations
    wr = db.execute(
        select(WorkRecord).where(WorkRecord.id == work_record_id).with_for_update()
    ).scalar_one_or_none()
    if wr is None:
        raise ValueError("work record not found")
    if wr.status != "attested":
        raise ValueError("work record is not attested")
    # Quarantine gate: never allocate evidence flagged as infected.
    if wr.evidence_file_id:
        ef = db.get(EvidenceFile, wr.evidence_file_id)
        if ef is not None and ef.scan_status == "infected":
            raise ValueError("evidence file is quarantined (infected)")
    used = allocated_quantity(db, work_record_id)
    remaining = Decimal(str(wr.quantity)) - used
    if qty > remaining:
        raise ValueError(
            f"insufficient evidence: requested {qty}, remaining {remaining}"
        )
    alloc = EvidenceAllocation(
        work_record_id=work_record_id,
        invoice_line_id=invoice_line_id,
        reconciliation_run_id=run_id,
        quantity=qty,
        status="reserved",
    )
    db.add(alloc)
    db.flush()
    return alloc


def consume_allocation(db: Session, allocation_id: str) -> None:
    alloc = db.get(EvidenceAllocation, allocation_id)
    if alloc is None:
        raise ValueError("allocation not found")
    alloc.status = "consumed"


def release_allocation(db: Session, allocation_id: str) -> None:
    alloc = db.get(EvidenceAllocation, allocation_id)
    if alloc is None:
        raise ValueError("allocation not found")
    alloc.status = "released"
    alloc.released_at = __import__("datetime").datetime.now(
        __import__("datetime").timezone.utc
    )
