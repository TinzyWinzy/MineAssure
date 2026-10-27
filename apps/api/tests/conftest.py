"""Real PostgreSQL fixtures; never run these tests against a customer database."""

import os
import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://mineassure:mineassure@localhost:5432/mineassure_test",
)
if not TEST_DATABASE_URL.rsplit("/", 1)[-1].split("?")[0].endswith("_test"):
    raise RuntimeError(
        "TEST_DATABASE_URL must name an isolated database ending in _test"
    )
os.environ["DATABASE_URL"] = TEST_DATABASE_URL

from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from alembic import command
from app.auth import create_access_token, hash_password
from app.db import engine, get_db
from app.models import (
    Contract,
    Contractor,
    ContractVersion,
    Invoice,
    InvoiceLine,
    Membership,
    Organisation,
    RateLine,
    Site,
    User,
    WorkRecord,
)


@pytest.fixture(scope="session")
def migrated_database():
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.set_main_option(
        "script_location", str(Path(__file__).resolve().parents[1] / "alembic")
    )
    command.upgrade(config, "head")


@pytest.fixture
def db(migrated_database):
    with engine.connect() as connection:
        transaction = connection.begin()
        session = Session(bind=connection, join_transaction_mode="create_savepoint")
        yield session
        session.close()
        transaction.rollback()


@pytest.fixture
def client(db):
    from app.main import app

    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def pilot(db):
    prefix = uuid4().hex[:12]
    ident = lambda name: f"test-{prefix}-{name}"
    org, foreign_org = ident("org"), ident("foreign-org")
    site, other_site = ident("site"), ident("other-site")
    db.add_all(
        [
            Organisation(id=org, name="Synthetic test mine"),
            Organisation(id=foreign_org, name="Other tenant"),
        ]
    )
    db.flush()
    db.add_all(
        [
            Site(id=site, org_id=org, name="Pilot"),
            Site(id=other_site, org_id=org, name="Unassigned"),
        ]
    )
    db.flush()
    users = {}
    password = hash_password("demo")
    for role in (
        "ap_analyst",
        "finance_approver",
        "auditor",
        "operations_verifier",
        "contract_preparer",
        "contract_approver",
        "partner_readonly",
    ):
        uid = ident(role)
        user = User(id=uid, email=f"{uid}@demo.local", hashed_password=password)
        db.add(user)
        db.flush()
        db.add(Membership(user_id=uid, org_id=org, site_id=site, role=role))
        users[role] = uid
    outsider = ident("outsider")
    db.add(User(id=outsider, email=f"{outsider}@demo.local", hashed_password=password))
    db.flush()
    db.add(
        Membership(
            user_id=outsider, org_id=foreign_org, site_id=None, role="finance_approver"
        )
    )
    contractor = Contractor(
        id=ident("supplier"), org_id=org, name="Synthetic Equipment"
    )
    db.add(contractor)
    db.flush()
    contract = Contract(
        id=ident("contract"),
        org_id=org,
        site_id=site,
        contractor_id=contractor.id,
        title="Hourly equipment",
    )
    db.add(contract)
    db.flush()
    cv = ContractVersion(
        id=ident("cv"),
        contract_id=contract.id,
        version_no=1,
        status="approved",
        effective_from=datetime(2026, 1, 1, tzinfo=UTC),
        currency="USD",
        approved_by=users["contract_approver"],
    )
    db.add(cv)
    db.flush()
    db.add(
        RateLine(
            contract_version_id=cv.id,
            work_code="EQ-HIRE",
            unit="hour",
            rate=Decimal(240),
        )
    )
    db.flush()

    def invoice(
        name="A",
        hours="160",
        rate="250",
        ref="SHIFT-A",
        when=None,
        at_site=None,
        creator=None,
    ):
        inv = Invoice(
            id=ident(f"invoice-{name}"),
            org_id=org,
            site_id=at_site or site,
            contractor_id=contractor.id,
            contract_id=contract.id,
            supplier_invoice_no=ident(name),
            currency="USD",
            created_by=creator or users["ap_analyst"],
        )
        db.add(inv)
        db.flush()
        line = InvoiceLine(
            id=ident(f"line-{name}"),
            invoice_id=inv.id,
            line_no=1,
            work_code="EQ-HIRE",
            service_date=when or datetime(2026, 10, 10, tzinfo=UTC),
            quantity=Decimal(hours),
            unit="hour",
            unit_price=Decimal(rate),
            amount=Decimal(hours) * Decimal(rate),
            work_reference=ref,
        )
        db.add(line)
        db.flush()
        return inv, line

    def evidence(name="A", hours="145", ref="SHIFT-A", status="attested", when=None):
        record = WorkRecord(
            id=ident(f"work-{name}"),
            org_id=org,
            site_id=site,
            contractor_id=contractor.id,
            contract_id=contract.id,
            work_code="EQ-HIRE",
            work_reference=ref,
            quantity=Decimal(hours),
            unit="hour",
            service_date=when or datetime(2026, 10, 10, tzinfo=UTC),
            status=status,
            attested_by=users["operations_verifier"] if status == "attested" else None,
        )
        db.add(record)
        db.flush()
        return record

    def headers(role="ap_analyst"):
        uid = outsider if role == "outsider" else users[role]
        # Membership claims deliberately empty: authorization must load current DB grants.
        return {"Authorization": f"Bearer {create_access_token(uid, [])}"}

    return {
        "org": org,
        "site": site,
        "other_site": other_site,
        "foreign_org": foreign_org,
        "contract": contract,
        "cv": cv,
        "users": users,
        "outsider": outsider,
        "headers": headers,
        "invoice": invoice,
        "evidence": evidence,
        "id": ident,
    }
