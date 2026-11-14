"""Add explicit snapshot ancestry and destination operational views."""

import sqlalchemy as sa
from alembic import op


revision = "0002_snapshot_integrity"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    snapshot_columns = {column["name"] for column in inspector.get_columns("state_snapshots")}
    if "parent_snapshot_id" not in snapshot_columns:
        with op.batch_alter_table("state_snapshots") as batch_op:
            batch_op.add_column(sa.Column("parent_snapshot_id", sa.String(length=36), nullable=True))
            batch_op.create_foreign_key(
                "fk_state_snapshots_parent_snapshot",
                "state_snapshots",
                ["parent_snapshot_id"],
                ["id"],
                ondelete="RESTRICT",
            )

    if "destination_snapshot_states" not in inspector.get_table_names():
        op.create_table(
            "destination_snapshot_states",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("destination_id", sa.String(length=36), nullable=False),
            sa.Column("snapshot_id", sa.String(length=36), nullable=False),
            sa.Column("operational_status", sa.Enum(
                "ACTIVE", "DEGRADED", "OFFLINE", "BLOCKED", "RESTRICTED",
                "OPEN", "LIMITED", "CLOSED", name="operationalstatusenum",
            ), nullable=False),
            sa.Column("suitability_score", sa.Float(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["destination_id"], ["destinations.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["snapshot_id"], ["state_snapshots.id"], ondelete="RESTRICT"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("destination_id", "snapshot_id", name="uq_destination_snapshot_state"),
        )
        op.create_index("ix_destination_snapshot_states_destination_id", "destination_snapshot_states", ["destination_id"])
        op.create_index("ix_destination_snapshot_states_snapshot_id", "destination_snapshot_states", ["snapshot_id"])


def downgrade() -> None:
    raise RuntimeError("Snapshot integrity migration is non-destructive; use a disposable database to remove it.")
