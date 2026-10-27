"""Scoped durable jobs with expiring claims and idempotency.

Revision ID: 0005
Revises: 0004
"""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("job_runs", sa.Column("org_id", sa.String(), sa.ForeignKey("organisations.id")))
    op.add_column("job_runs", sa.Column("site_id", sa.String(), sa.ForeignKey("sites.id")))
    op.add_column("job_runs", sa.Column("created_by", sa.String(), sa.ForeignKey("users.id")))
    op.add_column("job_runs", sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("job_runs", sa.Column("available_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.add_column("job_runs", sa.Column("lease_until", sa.DateTime(timezone=True)))
    op.add_column("job_runs", sa.Column("lease_token", sa.String()))
    op.create_index("ix_job_runs_org_id", "job_runs", ["org_id"])
    op.create_index("ix_job_runs_site_id", "job_runs", ["site_id"])
    op.create_unique_constraint("uq_job_idempotency", "job_runs", ["org_id", "site_id", "kind", "idempotency_key"])
    # The earlier scaffold could contain jobs with no verifiable actor or scope.
    op.execute("UPDATE job_runs SET status='failed', result='Legacy unscoped job quarantined' WHERE org_id IS NULL")


def downgrade():
    op.drop_constraint("uq_job_idempotency", "job_runs", type_="unique")
    op.drop_index("ix_job_runs_site_id", table_name="job_runs")
    op.drop_index("ix_job_runs_org_id", table_name="job_runs")
    for name in ("lease_token", "lease_until", "available_at", "attempts", "created_by", "site_id", "org_id"):
        op.drop_column("job_runs", name)
