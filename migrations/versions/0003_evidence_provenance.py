"""Make hazard evidence provenance machine-readable and thresholds optional."""

import sqlalchemy as sa
from alembic import op


revision = "0003_evidence_provenance"
down_revision = "0002_snapshot_integrity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("hazard_evidence")}
    if "provenance_type" not in columns or "source_entity_id" not in columns:
        with op.batch_alter_table("hazard_evidence") as batch_op:
            if "threshold_value" in columns:
                batch_op.alter_column("threshold_value", existing_type=sa.Float(), nullable=True)
            if "provenance_type" not in columns:
                batch_op.add_column(sa.Column("provenance_type", sa.String(length=50), nullable=True))
            if "source_entity_id" not in columns:
                batch_op.add_column(sa.Column("source_entity_id", sa.String(length=36), nullable=True))

    op.execute("UPDATE hazard_evidence SET provenance_type = 'SCENARIO_INPUT' WHERE provenance_type IS NULL")


def downgrade() -> None:
    raise RuntimeError("Evidence provenance migration is non-destructive; use a disposable database to remove it.")
