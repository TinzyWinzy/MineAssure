"""Real PostgreSQL row-lock contention and ledger conservation tests."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from decimal import Decimal
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.db import engine
from app.models import EvidenceAllocation, Organisation, Site, WorkRecord
from app.services.allocation import reserve_allocation


def test_concurrent_worker_claim_has_one_owner(migrated_database):
    from app.models import JobRun
    from app.worker import claim_job

    suffix = uuid4().hex
    org, site, job_id = f"org-{suffix}", f"site-{suffix}", f"job-{suffix}"
    with Session(engine) as db:
        db.add(Organisation(id=org, name="Synthetic job contention"))
        db.flush()
        db.add(Site(id=site, org_id=org, name="Synthetic site"))
        db.flush()
        db.add(JobRun(id=job_id, org_id=org, site_id=site, kind="reconciliation"))
        db.commit()
    barrier = Barrier(2)

    def claim(_):
        barrier.wait(timeout=10)
        return claim_job(lambda: Session(engine))

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(claim, range(2)))
    assert sum(outcome is not None for outcome in outcomes) == 1
    with Session(engine) as db:
        job = db.get(JobRun, job_id)
        assert job.status == "running" and job.attempts == 1
        job.status = "failed"
        db.commit()


def test_concurrent_allocation(migrated_database):
    suffix = uuid4().hex
    org, site, work = f"org-{suffix}", f"site-{suffix}", f"work-{suffix}"
    with Session(engine) as db:
        db.add(Organisation(id=org, name="Synthetic concurrent test"))
        db.flush()
        db.add(Site(id=site, org_id=org, name="Synthetic site"))
        db.flush()
        db.add(
            WorkRecord(
                id=work,
                org_id=org,
                site_id=site,
                work_code="EQ-HIRE",
                work_reference=suffix,
                quantity=Decimal(10),
                unit="hour",
                service_date=datetime(2026, 1, 1, tzinfo=UTC),
                status="attested",
            )
        )
        db.commit()
    barrier = Barrier(2)

    def allocate(index):
        with Session(engine) as db:
            barrier.wait(timeout=10)
            try:
                reserve_allocation(
                    db, work, f"line-{suffix}-{index}", None, Decimal(10)
                )
                db.commit()
                return "allocated"
            except ValueError as error:
                db.rollback()
                assert "insufficient" in str(error).lower()
                return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(allocate, range(2)))
    assert sorted(outcomes) == ["allocated", "conflict"]
    with Session(engine) as db:
        rows = (
            db.query(EvidenceAllocation)
            .filter(
                EvidenceAllocation.work_record_id == work,
                EvidenceAllocation.status.in_(["reserved", "consumed"]),
            )
            .all()
        )
        assert sum((row.quantity for row in rows), Decimal(0)) == 10


@pytest.mark.parametrize("quantity", ["0", "-1", "NaN", "Infinity"])
def test_invalid_allocation_quantity(db, pilot, quantity):
    work = pilot["evidence"]()
    with pytest.raises(ValueError):
        reserve_allocation(db, work.id, "test-line", None, Decimal(quantity))
