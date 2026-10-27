"""PostgreSQL-backed worker: python -m app.worker [--once].

Claim commits a bounded lease. Processing locks the job and atomically commits
the reconciliation and completion, so a process crash rolls back all postings.
Expired claims are replayed with the same run idempotency key.
"""

import argparse
import json
import logging
import time
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import and_, or_

from app.db import SessionLocal
from app.models import Invoice, JobRun, Membership, User
from app.routers.jobs import invoice_hash
from app.routers.persistence import CreateRunIn, reconcile_invoice
from app.services.access import audit

logger = logging.getLogger("mineassure.worker")
MAX_ATTEMPTS = 3
LEASE_SECONDS = 300


def claim_job(session_factory=SessionLocal, now=None):
    now = now or datetime.now(UTC)
    with session_factory() as db, db.begin():
        jobs = (
            db.query(JobRun)
            .filter(
                JobRun.kind == "reconciliation",
                JobRun.org_id.is_not(None),
                or_(
                    and_(JobRun.status == "queued", JobRun.available_at <= now),
                    and_(JobRun.status == "running", JobRun.lease_until <= now),
                ),
            )
            .order_by(JobRun.created_at, JobRun.id)
            .with_for_update(skip_locked=True)
        )
        for job in jobs:
            if job.attempts >= MAX_ATTEMPTS:
                job.status, job.completed_at = "failed", now
                job.lease_until, job.lease_token = None, None
                job.result = json.dumps(
                    {"message": "Retry limit reached after interrupted processing"}
                )
                continue
            job.status = "running"
            job.attempts += 1
            job.lease_until = now + timedelta(seconds=LEASE_SECONDS)
            job.lease_token = str(uuid4())
            return job.id, job.lease_token
    return None


def process_claim(claim, session_factory=SessionLocal):
    job_id, token = claim
    try:
        with session_factory() as db, db.begin():
            job = db.query(JobRun).filter_by(id=job_id).with_for_update().one()
            if job.status != "running" or job.lease_token != token:
                return False
            actor = db.get(User, job.created_by)
            if not actor or not actor.is_active:
                raise HTTPException(403, "Submitting account no longer active")
            actor._memberships = [
                fields
                for membership in db.query(Membership).filter_by(user_id=actor.id)
                for fields in [
                    {
                        "org_id": membership.org_id,
                        "site_id": membership.site_id,
                        "role": membership.role,
                    }
                ]
            ]
            payload = json.loads(job.payload)
            invoice = (
                db.query(Invoice)
                .filter_by(id=payload["invoice_id"])
                .with_for_update()
                .first()
            )
            if (
                not invoice
                or invoice.org_id != job.org_id
                or invoice.site_id != job.site_id
            ):
                raise HTTPException(404, "Invoice no longer available in job scope")
            if invoice_hash(db, invoice) != payload["invoice_hash"]:
                raise HTTPException(409, "Invoice changed after job submission")
            run = reconcile_invoice(
                CreateRunIn(
                    org_id=job.org_id,
                    site_id=job.site_id,
                    invoice_id=invoice.id,
                    idempotency_key="job-" + job.id,
                ),
                actor,
                db,
                commit=False,
            )
            job.status, job.completed_at = "completed", datetime.now(UTC)
            job.result = json.dumps({"run_id": run["id"]})
            job.lease_until, job.lease_token = None, None
            audit(
                db,
                actor,
                job,
                "job.completed",
                {"run_id": run["id"], "attempts": job.attempts},
            )
        return True
    except Exception as exc:
        # Error text from DB/drivers can contain connection/source information.
        # Persist only safe domain errors or a generic retry message.
        permanent = isinstance(exc, HTTPException)
        logger.exception("Job %s failed", job_id)
        with session_factory() as db, db.begin():
            job = db.query(JobRun).filter_by(id=job_id).with_for_update().one()
            if job.status != "running" or job.lease_token != token:
                return False
            exhausted = job.attempts >= MAX_ATTEMPTS
            job.status = "failed" if permanent or exhausted else "queued"
            job.available_at = datetime.now(UTC) + timedelta(seconds=2**job.attempts)
            job.completed_at = datetime.now(UTC) if job.status == "failed" else None
            job.lease_until, job.lease_token = None, None
            job.result = json.dumps(
                {
                    "message": str(exc.detail)
                    if permanent
                    else "Processing failed; retry scheduled"
                    if not exhausted
                    else "Retry limit reached"
                }
            )
        return False


def run_once(session_factory=SessionLocal):
    claim = claim_job(session_factory)
    if claim:
        process_claim(claim, session_factory)
    return claim is not None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    while True:
        try:
            worked = run_once()
        except Exception:
            logger.exception("Worker could not poll the database")
            worked = False
        if args.once:
            break
        if not worked:
            time.sleep(1)


if __name__ == "__main__":
    main()
