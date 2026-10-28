"""Source retention purge and removal of the decorative scan flag.

Revision ID: 0010
Revises: 0009

`evidence_files.scan_status` implied a malware-scanning control that no code
implemented. The table is not written by any workflow, so the column defaulted to
"pending" forever. Removing it keeps the schema honest; quarantine must return
with a real scanner and a writer.

`import_batches.purged_at/purged_by` record an explicit, audited removal of the
original uploaded bytes while preserving checksum, normalised rows, errors and
record lineage.
"""

import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("import_batches", sa.Column("purged_at", sa.DateTime(timezone=True)))
    op.add_column("import_batches", sa.Column("purged_by", sa.String()))
    op.drop_column("evidence_files", "scan_status")


def downgrade():
    op.add_column(
        "evidence_files",
        sa.Column("scan_status", sa.String(), nullable=False, server_default="pending"),
    )
    op.alter_column("evidence_files", "scan_status", server_default=None)
    op.drop_column("import_batches", "purged_by")
    op.drop_column("import_batches", "purged_at")
