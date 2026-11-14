"""Add provenance-preserving field observations and reconciliation status."""

import sqlalchemy as sa
from alembic import op


revision = "0005_field_observations"
down_revision = "0004_route_validity_windows"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "field_observations" in inspector.get_table_names():
        return
    op.create_table(
        "field_observations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("snapshot_id", sa.String(length=36), nullable=False),
        sa.Column("observation_type", sa.String(length=50), nullable=False),
        sa.Column("target_type", sa.String(length=50), nullable=False),
        sa.Column("target_id", sa.String(length=36), nullable=False),
        sa.Column("observed_state", sa.String(length=100), nullable=False),
        sa.Column("observed_value", sa.Float(), nullable=True),
        sa.Column("unit", sa.String(length=50), nullable=True),
        sa.Column("observed_at", sa.DateTime(), nullable=False),
        sa.Column("source_reference", sa.String(length=255), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("quality_status", sa.String(length=50), nullable=False, server_default="PENDING_REVIEW"),
        sa.Column("reconciliation_status", sa.String(length=50), nullable=False, server_default="NOT_RECONCILED"),
        sa.Column("reconciliation_result", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["snapshot_id"], ["state_snapshots.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_field_observations_snapshot_id", "field_observations", ["snapshot_id"])
    op.create_index("ix_field_observations_target_id", "field_observations", ["target_id"])


def downgrade() -> None:
    raise RuntimeError("Field observation migration is non-destructive; use a disposable database to remove it.")
