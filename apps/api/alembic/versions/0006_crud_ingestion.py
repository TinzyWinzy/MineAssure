"""Revision-protected draft CRUD and preserved staged file inputs.

Revision ID: 0006
Revises: 0005
"""
import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade():
    for table in ("contractors", "contracts", "work_records", "invoices"):
        op.add_column(table, sa.Column("revision", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("work_records", sa.Column("import_batch_id", sa.String(), sa.ForeignKey("import_batches.id")))
    op.create_index("ix_work_records_import_batch_id", "work_records", ["import_batch_id"])
    for name, kind in (("source_bytes", sa.LargeBinary()), ("mapping_json", sa.Text()), ("normalized_json", sa.Text())):
        op.add_column("import_batches", sa.Column(name, kind))


def downgrade():
    for name in ("normalized_json", "mapping_json", "source_bytes"):
        op.drop_column("import_batches", name)
    op.drop_index("ix_work_records_import_batch_id", table_name="work_records")
    op.drop_column("work_records", "import_batch_id")
    for table in ("invoices", "work_records", "contracts", "contractors"):
        op.drop_column(table, "revision")
