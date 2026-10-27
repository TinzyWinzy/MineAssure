"""Per-user asymmetric signing keys and approval signatures.

Revision ID: 0008
Revises: 0007
"""
import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "user_signing_keys",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("algorithm", sa.String(), nullable=False, server_default="ECDSA-P256"),
        sa.Column("public_key_pem", sa.Text(), nullable=False),
        sa.Column("encrypted_private_key", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("approvals", sa.Column("signature", sa.Text(), nullable=True))
    op.add_column("approvals", sa.Column("signer_key_id", sa.String(), sa.ForeignKey("user_signing_keys.id"), nullable=True))


def downgrade():
    op.drop_column("approvals", "signer_key_id")
    op.drop_column("approvals", "signature")
    op.drop_table("user_signing_keys")