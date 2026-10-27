"""Attestation hashes for approvals and export batches.

Revision ID: 0007
Revises: 0006
"""
import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("approvals", sa.Column("attestation_hash", sa.String(), nullable=True))
    op.add_column("export_batches", sa.Column("attestation_hash", sa.String(), nullable=True))


def downgrade():
    op.drop_column("export_batches", "attestation_hash")
    op.drop_column("approvals", "attestation_hash")