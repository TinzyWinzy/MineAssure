"""Idempotent synthetic pilot seed."""

from datetime import UTC, datetime
from decimal import Decimal

from app.auth import hash_password
from app.config import settings
from app.db import SessionLocal
from app.models import (
    Contract,
    Contractor,
    ContractVersion,
    Invoice,
    InvoiceLine,
    Membership,
    Organisation,
    RateLine,
    ReconciliationRun,
    Site,
    User,
    WorkRecord,
)


def seed_demo(db=None):
    if settings.environment not in ("development", "test"):
        raise RuntimeError("Synthetic seed is restricted to development/test")
    owns_session = db is None
    db = db or SessionLocal()

    def add_once(model, key, **values):
        row = db.get(model, key)
        if row is None and model is Membership:
            row = db.query(Membership).filter_by(**values).first()
        if row is None:
            row = model(id=key, **values)
            db.add(row)
            db.flush()
        return row

    try:
        add_once(Organisation, "org-demo", name="Demo Mine Operations")
        add_once(Site, "site-1", org_id="org-demo", name="Mopane Pilot Site")
        accounts = [
            ("admin", "tenant_admin", None),
            ("preparer", "contract_preparer", "site-1"),
            ("approver", "contract_approver", "site-1"),
            ("verifier", "operations_verifier", "site-1"),
            ("verifier2", "operations_verifier", "site-1"),
            ("ap", "ap_analyst", "site-1"),
            ("finance", "finance_approver", "site-1"),
            ("auditor", "auditor", "site-1"),
            ("partner", "partner_readonly", "site-1"),
        ]
        for name, role, site in accounts:
            uid = "user-verifier2" if name == "verifier2" else "user-" + role
            if not db.get(User, uid):
                add_once(
                    User,
                    uid,
                    email=name + "@demo.local",
                    hashed_password=hash_password("demo"),
                )
            add_once(
                Membership,
                "mem-" + name,
                user_id=uid,
                org_id="org-demo",
                site_id=site,
                role=role,
            )
        add_once(Contractor, "ctr-1", org_id="org-demo", name="Acme Equipment Hire")
        add_once(
            Contract,
            "contract-1",
            org_id="org-demo",
            site_id="site-1",
            contractor_id="ctr-1",
            title="Equipment hire hourly services",
        )
        add_once(
            ContractVersion,
            "cv-1",
            contract_id="contract-1",
            version_no=1,
            status="approved",
            effective_from=datetime(2026, 1, 1, tzinfo=UTC),
            currency="USD",
            pricing_type="hourly_hire",
            created_by="user-contract_preparer",
            approved_by="user-contract_approver",
            approved_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        add_once(
            RateLine,
            "rl-1",
            contract_version_id="cv-1",
            work_code="EQ-HIRE",
            unit="hour",
            rate=Decimal(240),
            cap_hours=Decimal(200),
        )
        day = datetime(2026, 10, 10, tzinfo=UTC)
        add_once(
            WorkRecord,
            "wr-demo-a",
            org_id="org-demo",
            site_id="site-1",
            contract_id="contract-1",
            contractor_id="ctr-1",
            work_code="EQ-HIRE",
            work_reference="SHIFT-1010",
            quantity=Decimal(145),
            unit="hour",
            service_date=day,
            status="attested",
            created_by="user-tenant_admin",
            attested_by="user-operations_verifier",
            attested_at=day,
        )
        for key, ref, qty, rate, workref in [
            ("a", "ACME-2026-041", "160", "250", "SHIFT-1010"),
            ("b", "ACME-2026-042", "10", "240", "MISSING-SHIFT"),
            ("c", "ACME-2026-043", "20", "240", "SHIFT-1010"),
        ]:
            inv = add_once(
                Invoice,
                "inv-demo-" + key,
                org_id="org-demo",
                site_id="site-1",
                contractor_id="ctr-1",
                contract_id="contract-1",
                supplier_invoice_no=ref,
                currency="USD",
                status="imported",
                created_by="user-ap_analyst",
            )
            add_once(
                InvoiceLine,
                "line-demo-" + key,
                invoice_id=inv.id,
                line_no=1,
                work_code="EQ-HIRE",
                description="Equipment hire hours",
                quantity=Decimal(qty),
                unit="hour",
                unit_price=Decimal(rate),
                amount=Decimal(qty) * Decimal(rate),
                service_date=day,
                work_reference=workref,
            )
        db.commit()
        from app.routers.persistence import CreateRunIn, create_run

        actor = db.get(User, "user-ap_analyst")
        actor._memberships = [
            {"org_id": "org-demo", "site_id": "site-1", "role": "ap_analyst"}
        ]
        for key in ("a", "b", "c"):
            invoice_id = "inv-demo-" + key
            if not db.query(ReconciliationRun).filter_by(invoice_id=invoice_id).first():
                create_run(
                    CreateRunIn(
                        org_id="org-demo",
                        site_id="site-1",
                        invoice_id=invoice_id,
                        idempotency_key="seed-" + key,
                    ),
                    actor,
                    db,
                )
    finally:
        if owns_session:
            db.close()


if __name__ == "__main__":
    seed_demo()
    print("Synthetic demo seeded (existing records preserved)")
