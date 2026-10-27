"""Add workflow provenance and export uniqueness (reversible).

Revision ID: 0003
Revises: 30e7c63b640f
"""

import sqlalchemy as sa

from alembic import op

revision = "0003"
down_revision = "30e7c63b640f"
branch_labels = None
depends_on = None

ADDITIONS = {
    "contract_versions": [("created_by", sa.String())],
    "work_records": [("work_reference", sa.String()), ("created_by", sa.String())],
    "import_batches": [
        ("source_text", sa.Text()),
        ("errors_json", sa.Text()),
        ("created_by", sa.String()),
    ],
    "invoices": [("created_by", sa.String())],
    "reconciliation_runs": [
        ("input_snapshot", sa.Text()),
        ("created_by", sa.String()),
        ("idempotency_key", sa.String()),
    ],
    "export_batches": [
        ("run_id", sa.String()),
        ("idempotency_key", sa.String()),
        ("artifact_text", sa.Text()),
    ],
}


def upgrade():
    for table, columns in ADDITIONS.items():
        for name, kind in columns:
            op.add_column(table, sa.Column(name, kind, nullable=True))
    op.add_column(
        "reconciliation_runs",
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_index(
        "ix_work_records_work_reference", "work_records", ["work_reference"]
    )
    with op.batch_alter_table("approvals") as batch:
        batch.create_unique_constraint(
            "uq_approval_run_line", ["run_id", "invoice_line_id"]
        )
    with op.batch_alter_table("export_batches") as batch:
        batch.create_unique_constraint("uq_export_run", ["run_id"])
        batch.create_foreign_key(
            "fk_export_run", "reconciliation_runs", ["run_id"], ["id"]
        )


def downgrade():
    with op.batch_alter_table("export_batches") as batch:
        batch.drop_constraint("fk_export_run", type_="foreignkey")
        batch.drop_constraint("uq_export_run", type_="unique")
    with op.batch_alter_table("approvals") as batch:
        batch.drop_constraint("uq_approval_run_line", type_="unique")
    op.drop_index("ix_work_records_work_reference", table_name="work_records")
    op.drop_column("reconciliation_runs", "version")
    for table, columns in reversed(list(ADDITIONS.items())):
        for name, _ in reversed(columns):
            op.drop_column(table, name)
