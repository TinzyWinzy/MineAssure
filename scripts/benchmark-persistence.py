"""Measure 1,000-line persisted reconciliation on an isolated test database.

Fixture setup and ingestion are excluded. The measured call includes rate and
evidence queries, row locks, allocations, snapshots, findings/cases and output.
All benchmark rows roll back after the measurement.
"""

import json
import os
import platform
import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from time import perf_counter
from uuid import uuid4

root = Path(__file__).resolve().parents[1]
config = json.loads((root / ".local/config.json").read_text(encoding="utf-8-sig"))
os.environ["DATABASE_URL"] = f"postgresql+psycopg://mineassure:{config['database_password']}@127.0.0.1:{config['database_port']}/mineassure_test"
os.environ["ENVIRONMENT"] = "test"
sys.path.insert(0, str(root / "apps/api"))

from sqlalchemy.orm import Session  # noqa: E402
from app.db import engine  # noqa: E402
from app.models import (Organisation, Site, User, Contractor, Contract, ContractVersion,
                        RateLine, Invoice, InvoiceLine, WorkRecord, EvidenceAllocation)  # noqa: E402
from app.routers.persistence import CreateRunIn, reconcile_invoice  # noqa: E402

prefix = "benchmark-" + uuid4().hex
day = datetime(2026, 10, 10, tzinfo=UTC)
with engine.connect() as connection:
    transaction = connection.begin()
    db = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        db.add(Organisation(id=prefix, name="Synthetic benchmark"))
        db.flush()
        db.add(Site(id=prefix, org_id=prefix, name="Synthetic benchmark"))
        actor = User(id=prefix, email=prefix + "@demo.local", hashed_password="login-disabled")
        actor._memberships = [{"org_id": prefix, "site_id": prefix, "role": "ap_analyst"}]
        db.add(actor)
        db.add(Contractor(id=prefix, org_id=prefix, name="Synthetic benchmark"))
        db.flush()
        db.add(Contract(id=prefix, org_id=prefix, site_id=prefix, contractor_id=prefix, title="Benchmark hourly hire"))
        db.flush()
        db.add(ContractVersion(id=prefix, contract_id=prefix, version_no=1, status="approved", effective_from=day, currency="USD"))
        db.flush()
        db.add(RateLine(contract_version_id=prefix, work_code="EQ-HIRE", unit="hour", rate=Decimal(240)))
        db.add(Invoice(id=prefix, org_id=prefix, site_id=prefix, contractor_id=prefix, contract_id=prefix,
                       supplier_invoice_no=prefix, created_by=actor.id, currency="USD"))
        db.flush()
        for index in range(1000):
            reference = f"{prefix}-{index}"
            db.add(InvoiceLine(invoice_id=prefix, line_no=index + 1, work_code="EQ-HIRE", service_date=day,
                               quantity=Decimal(160), unit="hour", unit_price=Decimal(250), amount=Decimal(40000), work_reference=reference))
            db.add(WorkRecord(org_id=prefix, site_id=prefix, contractor_id=prefix, contract_id=prefix,
                              work_code="EQ-HIRE", work_reference=reference, service_date=day, quantity=Decimal(145),
                              unit="hour", status="attested", attested_by="independent-synthetic-verifier"))
        db.flush()
        started = perf_counter()
        result = reconcile_invoice(CreateRunIn(org_id=prefix, site_id=prefix, invoice_id=prefix), actor, db)
        elapsed = perf_counter() - started
        assert len(result["results"]) == 1000
        assert all(Decimal(row["supported_amount"]) == 34800 and Decimal(row["quantified_variance"]) == 5200 for row in result["results"])
        assert db.query(EvidenceAllocation).filter_by(reconciliation_run_id=result["id"], status="reserved").count() == 1000
        report = {"scope": "persisted reconciliation; excludes fixture setup, file ingestion and network HTTP",
                  "lines": 1000, "seconds": round(elapsed, 6), "meets_60_second_target": elapsed <= 60,
                  "python": platform.python_version(), "platform": platform.platform(), "processor": platform.processor(),
                  "postgresql": connection.exec_driver_sql("SHOW server_version").scalar(), "benchmark_rows_rolled_back": True}
    finally:
        db.close()
        transaction.rollback()
(root / ".local/benchmark-report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report, indent=2))
