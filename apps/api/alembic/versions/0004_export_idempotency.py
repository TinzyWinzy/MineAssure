"""Scope export idempotency uniqueness to organisation/site.

Revision ID: 0004
Revises: 0003
"""

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("export_batches") as batch:
        batch.create_unique_constraint(
            "uq_export_idempotency", ["org_id", "site_id", "idempotency_key"]
        )


def downgrade():
    with op.batch_alter_table("export_batches") as batch:
        batch.drop_constraint("uq_export_idempotency", type_="unique")
