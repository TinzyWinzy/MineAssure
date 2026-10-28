"""MineAssure domain models.

All monetary values are stored as PostgreSQL NUMERIC and handled as Python Decimal.
Never use float for financial business logic.
"""

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.sql import func

from app.db import Base


def _uuid() -> str:
    import uuid

    return str(uuid.uuid4())


# ---------------- Organisation / Site / Users ----------------


class Organisation(Base):
    __tablename__ = "organisations"
    id = Column(String, primary_key=True, default=_uuid)
    name = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Site(Base):
    __tablename__ = "sites"
    id = Column(String, primary_key=True, default=_uuid)
    org_id = Column(String, ForeignKey("organisations.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, default=_uuid)
    email = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Membership(Base):
    __tablename__ = "memberships"
    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    org_id = Column(String, ForeignKey("organisations.id"), nullable=False, index=True)
    role = Column(String, nullable=False)
    site_id = Column(String, ForeignKey("sites.id"), nullable=True, index=True)
    __table_args__ = (
        UniqueConstraint("user_id", "org_id", "site_id", "role", name="uq_membership"),
    )


# ---------------- Contractors ----------------


class Contractor(Base):
    __tablename__ = "contractors"
    id = Column(String, primary_key=True, default=_uuid)
    org_id = Column(String, ForeignKey("organisations.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    revision = Column(Integer, nullable=False, default=1, server_default="1")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ---------------- Contracts ----------------


class Contract(Base):
    __tablename__ = "contracts"
    id = Column(String, primary_key=True, default=_uuid)
    org_id = Column(String, ForeignKey("organisations.id"), nullable=False, index=True)
    site_id = Column(String, ForeignKey("sites.id"), nullable=False, index=True)
    contractor_id = Column(
        String, ForeignKey("contractors.id"), nullable=False, index=True
    )
    title = Column(String, nullable=False)
    revision = Column(Integer, nullable=False, default=1, server_default="1")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ContractVersion(Base):
    __tablename__ = "contract_versions"
    id = Column(String, primary_key=True, default=_uuid)
    contract_id = Column(String, ForeignKey("contracts.id"), nullable=False, index=True)
    version_no = Column(Integer, nullable=False)
    status = Column(
        String, nullable=False, default="draft"
    )  # draft/approved/superseded
    effective_from = Column(DateTime(timezone=True), nullable=False)
    effective_to = Column(DateTime(timezone=True), nullable=True)
    currency = Column(String, nullable=False, default="USD")
    pricing_type = Column(String, nullable=False, default="hourly_hire")
    approved_by = Column(String, nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    content_hash = Column(String, nullable=True)
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        UniqueConstraint("contract_id", "version_no", name="uq_contract_version"),
    )


class RateLine(Base):
    __tablename__ = "rate_lines"
    id = Column(String, primary_key=True, default=_uuid)
    contract_version_id = Column(
        String, ForeignKey("contract_versions.id"), nullable=False, index=True
    )
    work_code = Column(String, nullable=False)
    unit = Column(String, nullable=False, default="hour")
    rate = Column(Numeric(18, 6), nullable=False)
    cap_hours = Column(Numeric(18, 6), nullable=True)
    minimum_hours = Column(Numeric(18, 6), nullable=True)
    standby_rate = Column(Numeric(18, 6), nullable=True)
    standby_explicit = Column(Boolean, default=False)
    minimum_explicit = Column(Boolean, default=False)
    effective_from = Column(DateTime(timezone=True), nullable=True)
    effective_to = Column(DateTime(timezone=True), nullable=True)


class ContractVariation(Base):
    __tablename__ = "contract_variations"
    id = Column(String, primary_key=True, default=_uuid)
    contract_id = Column(String, ForeignKey("contracts.id"), nullable=False, index=True)
    contract_version_id = Column(
        String, ForeignKey("contract_versions.id"), nullable=True
    )
    status = Column(String, nullable=False, default="draft")  # draft/approved
    description = Column(Text, nullable=True)
    rate_delta = Column(Numeric(18, 6), nullable=True)
    approved_by = Column(String, nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ---------------- Evidence ----------------


class EvidenceFile(Base):
    __tablename__ = "evidence_files"
    id = Column(String, primary_key=True, default=_uuid)
    org_id = Column(String, ForeignKey("organisations.id"), nullable=False, index=True)
    site_id = Column(String, ForeignKey("sites.id"), nullable=True, index=True)
    uploader_id = Column(String, nullable=True)
    object_key = Column(String, nullable=False)
    filename = Column(String, nullable=False)
    mime_type = Column(String, nullable=True)
    size_bytes = Column(Integer, nullable=True)
    sha256 = Column(String, nullable=False)
    # No scanner is implemented. Quarantine state must not be implied by a column
    # whose only value would be an unverified default.
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class WorkRecord(Base):
    __tablename__ = "work_records"
    id = Column(String, primary_key=True, default=_uuid)
    org_id = Column(String, ForeignKey("organisations.id"), nullable=False, index=True)
    site_id = Column(String, ForeignKey("sites.id"), nullable=False, index=True)
    contractor_id = Column(
        String, ForeignKey("contractors.id"), nullable=True, index=True
    )
    contract_id = Column(String, ForeignKey("contracts.id"), nullable=True, index=True)
    work_code = Column(String, nullable=False)
    work_reference = Column(String, nullable=True, index=True)
    created_by = Column(String, nullable=True)
    revision = Column(Integer, nullable=False, default=1, server_default="1")
    import_batch_id = Column(
        String, ForeignKey("import_batches.id"), nullable=True, index=True
    )
    quantity = Column(Numeric(18, 6), nullable=False)
    unit = Column(String, nullable=False, default="hour")
    service_date = Column(DateTime(timezone=True), nullable=False, index=True)
    status = Column(
        String, nullable=False, default="imported"
    )  # imported/attested/rejected
    evidence_file_id = Column(String, ForeignKey("evidence_files.id"), nullable=True)
    attested_by = Column(String, nullable=True)
    attested_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class EvidenceAllocation(Base):
    __tablename__ = "evidence_allocations"
    id = Column(String, primary_key=True, default=_uuid)
    work_record_id = Column(
        String, ForeignKey("work_records.id"), nullable=False, index=True
    )
    invoice_line_id = Column(String, nullable=True, index=True)
    reconciliation_run_id = Column(String, nullable=True, index=True)
    quantity = Column(Numeric(18, 6), nullable=False)
    status = Column(
        String, nullable=False, default="reserved"
    )  # reserved/consumed/released
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    released_at = Column(DateTime(timezone=True), nullable=True)


# ---------------- Invoices ----------------


class ImportBatch(Base):
    __tablename__ = "import_batches"
    id = Column(String, primary_key=True, default=_uuid)
    org_id = Column(String, ForeignKey("organisations.id"), nullable=False, index=True)
    site_id = Column(String, ForeignKey("sites.id"), nullable=True, index=True)
    kind = Column(String, nullable=False)  # work/invoice
    filename = Column(String, nullable=False)
    sha256 = Column(String, nullable=False)
    status = Column(String, nullable=False, default="staged")
    source_text = Column(Text, nullable=True)
    source_bytes = Column(LargeBinary, nullable=True)
    mapping_json = Column(Text, nullable=True)
    normalized_json = Column(Text, nullable=True)
    errors_json = Column(Text, nullable=True)
    created_by = Column(String, nullable=True)
    purged_at = Column(DateTime(timezone=True), nullable=True)
    purged_by = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Invoice(Base):
    __tablename__ = "invoices"
    id = Column(String, primary_key=True, default=_uuid)
    org_id = Column(String, ForeignKey("organisations.id"), nullable=False, index=True)
    site_id = Column(String, ForeignKey("sites.id"), nullable=False, index=True)
    contractor_id = Column(
        String, ForeignKey("contractors.id"), nullable=True, index=True
    )
    contract_id = Column(String, ForeignKey("contracts.id"), nullable=True, index=True)
    supplier_invoice_no = Column(String, nullable=False)
    period_start = Column(DateTime(timezone=True), nullable=True)
    period_end = Column(DateTime(timezone=True), nullable=True)
    currency = Column(String, nullable=False, default="USD")
    status = Column(String, nullable=False, default="imported")
    fingerprint = Column(String, nullable=True, index=True)
    created_by = Column(String, nullable=True)
    revision = Column(Integer, nullable=False, default=1, server_default="1")
    import_batch_id = Column(String, ForeignKey("import_batches.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        UniqueConstraint(
            "org_id", "contractor_id", "supplier_invoice_no", name="uq_invoice_ref"
        ),
    )


class InvoiceLine(Base):
    __tablename__ = "invoice_lines"
    id = Column(String, primary_key=True, default=_uuid)
    invoice_id = Column(String, ForeignKey("invoices.id"), nullable=False, index=True)
    line_no = Column(Integer, nullable=False)
    work_code = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    service_date = Column(DateTime(timezone=True), nullable=True, index=True)
    quantity = Column(Numeric(18, 6), nullable=False)
    unit = Column(String, nullable=False, default="hour")
    unit_price = Column(Numeric(18, 6), nullable=False)
    amount = Column(Numeric(18, 6), nullable=False)
    work_reference = Column(String, nullable=True)


# ---------------- Reconciliation ----------------


class ReconciliationRun(Base):
    __tablename__ = "reconciliation_runs"
    id = Column(String, primary_key=True, default=_uuid)
    org_id = Column(String, ForeignKey("organisations.id"), nullable=False, index=True)
    site_id = Column(String, ForeignKey("sites.id"), nullable=False, index=True)
    invoice_id = Column(String, ForeignKey("invoices.id"), nullable=False, index=True)
    contract_version_id = Column(
        String, ForeignKey("contract_versions.id"), nullable=True
    )
    rule_set_version = Column(String, nullable=False, default="1.0")
    input_hash = Column(String, nullable=True)
    input_snapshot = Column(Text, nullable=True)
    created_by = Column(String, nullable=True)
    version = Column(Integer, nullable=False, default=1)
    idempotency_key = Column(String, nullable=True)
    status = Column(String, nullable=False, default="completed")
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    is_current = Column(Boolean, default=True)


class ReconciliationLineResult(Base):
    __tablename__ = "reconciliation_line_results"
    id = Column(String, primary_key=True, default=_uuid)
    run_id = Column(
        String, ForeignKey("reconciliation_runs.id"), nullable=False, index=True
    )
    invoice_line_id = Column(
        String, ForeignKey("invoice_lines.id"), nullable=False, index=True
    )
    invoiced_amount = Column(Numeric(18, 6), nullable=False)
    supported_amount = Column(Numeric(18, 6), nullable=False, default=0)
    unverified_amount = Column(Numeric(18, 6), nullable=False, default=0)
    quantified_variance = Column(Numeric(18, 6), nullable=False, default=0)
    approved_amount = Column(Numeric(18, 6), nullable=False, default=0)
    explanation = Column(Text, nullable=True)
    evidence_refs = Column(Text, nullable=True)


class Finding(Base):
    __tablename__ = "findings"
    id = Column(String, primary_key=True, default=_uuid)
    run_id = Column(
        String, ForeignKey("reconciliation_runs.id"), nullable=False, index=True
    )
    invoice_line_id = Column(
        String, ForeignKey("invoice_lines.id"), nullable=False, index=True
    )
    rule_code = Column(String, nullable=False)  # R001..R008
    severity = Column(String, nullable=False, default="medium")
    status = Column(String, nullable=False, default="open")
    message = Column(Text, nullable=False)
    quantified_amount = Column(Numeric(18, 6), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ---------------- Client-side public keys ----------------


class UserPublicKey(Base):
    __tablename__ = "user_public_keys"
    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    spki_b64 = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    revoked_at = Column(DateTime(timezone=True), nullable=True)


# ---------------- Signing keys ----------------


class UserSigningKey(Base):
    __tablename__ = "user_signing_keys"
    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    algorithm = Column(String, nullable=False, default="ECDSA-P256")
    public_key_pem = Column(Text, nullable=False)
    encrypted_private_key = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    revoked_at = Column(DateTime(timezone=True), nullable=True)


# ---------------- Cases / Approvals ----------------


class Case(Base):
    __tablename__ = "cases"
    id = Column(String, primary_key=True, default=_uuid)
    org_id = Column(String, ForeignKey("organisations.id"), nullable=False, index=True)
    site_id = Column(String, ForeignKey("sites.id"), nullable=True, index=True)
    finding_id = Column(String, ForeignKey("findings.id"), nullable=True, index=True)
    assignee_id = Column(String, nullable=True)
    status = Column(String, nullable=False, default="open")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class CaseComment(Base):
    __tablename__ = "case_comments"
    id = Column(String, primary_key=True, default=_uuid)
    case_id = Column(String, ForeignKey("cases.id"), nullable=False, index=True)
    author_id = Column(String, nullable=False)
    body = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Approval(Base):
    __tablename__ = "approvals"
    id = Column(String, primary_key=True, default=_uuid)
    run_id = Column(
        String, ForeignKey("reconciliation_runs.id"), nullable=False, index=True
    )
    invoice_line_id = Column(
        String, ForeignKey("invoice_lines.id"), nullable=False, index=True
    )
    approver_id = Column(String, nullable=False)
    decision = Column(String, nullable=False)  # approved/rejected/override
    amount = Column(Numeric(18, 6), nullable=False)
    reason = Column(Text, nullable=True)
    version = Column(Integer, nullable=False, default=1)
    attestation_hash = Column(String, nullable=True)
    signature = Column(Text, nullable=True)
    signer_key_id = Column(String, ForeignKey("user_signing_keys.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        UniqueConstraint("run_id", "invoice_line_id", name="uq_approval_run_line"),
    )


# ---------------- Audit / Export ----------------


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id = Column(String, primary_key=True, default=_uuid)
    org_id = Column(String, nullable=True, index=True)
    site_id = Column(String, nullable=True, index=True)
    actor_id = Column(String, nullable=True)
    action = Column(String, nullable=False)
    entity_type = Column(String, nullable=False)
    entity_id = Column(String, nullable=False)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    request_id = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ExportBatch(Base):
    __tablename__ = "export_batches"
    id = Column(String, primary_key=True, default=_uuid)
    org_id = Column(String, ForeignKey("organisations.id"), nullable=False, index=True)
    site_id = Column(String, ForeignKey("sites.id"), nullable=True, index=True)
    status = Column(String, nullable=False, default="created")
    artifact_hash = Column(String, nullable=True)
    created_by = Column(String, nullable=True)
    run_id = Column(
        String, ForeignKey("reconciliation_runs.id"), nullable=True, unique=True
    )
    idempotency_key = Column(String, nullable=True)
    artifact_text = Column(Text, nullable=True)
    attestation_hash = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        UniqueConstraint(
            "org_id", "site_id", "idempotency_key", name="uq_export_idempotency"
        ),
    )


class ExportLine(Base):
    __tablename__ = "export_lines"
    id = Column(String, primary_key=True, default=_uuid)
    export_batch_id = Column(
        String, ForeignKey("export_batches.id"), nullable=False, index=True
    )
    invoice_line_id = Column(
        String, ForeignKey("invoice_lines.id"), nullable=False, index=True
    )
    approval_id = Column(String, ForeignKey("approvals.id"), nullable=True)
    amount_minor = Column(Integer, nullable=False)
    currency = Column(String, nullable=False, default="USD")
    provenance = Column(Text, nullable=True)


class JobRun(Base):
    __tablename__ = "job_runs"
    id = Column(String, primary_key=True, default=_uuid)
    kind = Column(String, nullable=False)
    status = Column(String, nullable=False, default="queued")
    payload = Column(Text, nullable=True)
    result = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    idempotency_key = Column(String, nullable=True, index=True)
    org_id = Column(String, ForeignKey("organisations.id"), nullable=True, index=True)
    site_id = Column(String, ForeignKey("sites.id"), nullable=True, index=True)
    created_by = Column(String, ForeignKey("users.id"), nullable=True)
    attempts = Column(Integer, nullable=False, default=0, server_default="0")
    available_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    lease_until = Column(DateTime(timezone=True), nullable=True)
    lease_token = Column(String, nullable=True)
    __table_args__ = (
        UniqueConstraint(
            "org_id", "site_id", "kind", "idempotency_key", name="uq_job_idempotency"
        ),
    )
