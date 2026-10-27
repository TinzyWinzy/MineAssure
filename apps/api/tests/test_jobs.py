import json
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.models import EvidenceAllocation, JobRun, Membership, ReconciliationRun
from app.worker import claim_job, process_claim, run_once


def enqueue(client, pilot, invoice, key="request"):
    return client.post(
        "/api/v1/jobs/reconciliation",
        headers=pilot["headers"](),
        json={
            "org_id": pilot["org"],
            "site_id": pilot["site"],
            "invoice_id": invoice.id,
            "idempotency_key": pilot["id"](key),
        },
    )


def factory(db):
    connection = db.connection()
    return lambda: Session(bind=connection, join_transaction_mode="create_savepoint")


def test_job_replay_commits_one_run_and_one_allocation(client, db, pilot):
    invoice, _ = pilot["invoice"]()
    work = pilot["evidence"]()
    response = enqueue(client, pilot, invoice)
    assert response.status_code == 202, response.text
    job_id = response.json()["id"]
    assert enqueue(client, pilot, invoice).json()["id"] == job_id
    assert enqueue(client, pilot, invoice, key="different").json()["id"] == job_id
    sessions = factory(db)
    claim = claim_job(sessions)
    assert claim and claim[0] == job_id
    with sessions() as check:
        saved = check.get(JobRun, job_id)
        assert (saved.status, saved.lease_token) == ("running", claim[1])
    processed = process_claim(claim, sessions)
    with sessions() as check:
        saved = check.get(JobRun, job_id)
        assert processed, (saved.status, saved.result)
    assert not process_claim(claim, sessions)
    completed = client.get(f"/api/v1/jobs/{job_id}", headers=pilot["headers"]())
    assert completed.status_code == 200, completed.text
    assert completed.json()["status"] == "completed"
    assert completed.json()["attempts"] == 1
    assert db.query(ReconciliationRun).filter_by(invoice_id=invoice.id).count() == 1
    assert (
        db.query(EvidenceAllocation)
        .filter_by(work_record_id=work.id, status="reserved")
        .count()
        == 1
    )
    assert enqueue(client, pilot, invoice).json()["id"] == job_id


def test_expired_claim_is_recovered_and_old_owner_cannot_post(client, db, pilot):
    invoice, _ = pilot["invoice"]()
    pilot["evidence"]()
    job_id = enqueue(client, pilot, invoice).json()["id"]
    sessions = factory(db)
    first = claim_job(sessions)
    second = claim_job(sessions, now=datetime.now(UTC) + timedelta(minutes=6))
    assert first[0] == second[0] == job_id and first[1] != second[1]
    assert not process_claim(first, sessions)
    assert process_claim(second, sessions)
    assert db.query(ReconciliationRun).filter_by(invoice_id=invoice.id).count() == 1


def test_job_reauthorizes_revoked_actor(client, db, pilot):
    invoice, _ = pilot["invoice"]()
    pilot["evidence"]()
    job_id = enqueue(client, pilot, invoice).json()["id"]
    db.query(Membership).filter_by(user_id=pilot["users"]["ap_analyst"]).delete()
    db.flush()
    assert run_once(factory(db))
    db.expire_all()
    job = db.get(JobRun, job_id)
    assert job.status == "failed"
    assert db.query(ReconciliationRun).filter_by(invoice_id=invoice.id).count() == 0
    assert (
        client.get(
            f"/api/v1/jobs/{job_id}", headers=pilot["headers"]("outsider")
        ).status_code
        == 403
    )


def test_worker_failure_rolls_back_and_retries(client, db, pilot, monkeypatch):
    from app import worker

    invoice, _ = pilot["invoice"]()
    work = pilot["evidence"]()
    job_id = enqueue(client, pilot, invoice).json()["id"]
    actual = worker.reconcile_invoice

    def fail_after_posting(*args, **kwargs):
        actual(*args, **kwargs)
        raise RuntimeError("Simulated connection loss after posting before commit")

    monkeypatch.setattr(worker, "reconcile_invoice", fail_after_posting)
    sessions = factory(db)
    assert not process_claim(claim_job(sessions), sessions)
    db.expire_all()
    assert db.get(JobRun, job_id).status == "queued"
    assert db.query(ReconciliationRun).filter_by(invoice_id=invoice.id).count() == 0
    assert db.query(EvidenceAllocation).filter_by(work_record_id=work.id).count() == 0
    monkeypatch.setattr(worker, "reconcile_invoice", actual)
    assert process_claim(
        claim_job(sessions, now=datetime.now(UTC) + timedelta(seconds=10)), sessions
    )
    assert db.query(ReconciliationRun).filter_by(invoice_id=invoice.id).count() == 1


def test_worker_crash_retry_limit_and_changed_input(client, db, pilot):
    invoice, _ = pilot["invoice"]()
    job_id = enqueue(client, pilot, invoice).json()["id"]
    sessions = factory(db)
    for attempt in range(3):
        assert claim_job(
            sessions, now=datetime.now(UTC) + timedelta(minutes=6 * attempt)
        )
    assert claim_job(sessions, now=datetime.now(UTC) + timedelta(minutes=20)) is None
    db.expire_all()
    assert db.get(JobRun, job_id).status == "failed"
    new_job = enqueue(client, pilot, invoice, key="new-request").json()["id"]
    invoice.currency = "OTHER"
    db.flush()
    assert run_once(sessions)
    db.expire_all()
    assert db.get(JobRun, new_job).status == "failed"
    assert "changed" in json.loads(db.get(JobRun, new_job).result)["message"]
