"""Add explicit route validity windows for time-dependent feasibility."""

import sqlalchemy as sa
from alembic import op


revision = "0004_route_validity_windows"
down_revision = "0003_evidence_provenance"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("route_plans")}
    with op.batch_alter_table("route_plans") as batch_op:
        if "valid_from_min" not in columns:
            batch_op.add_column(sa.Column("valid_from_min", sa.Float(), nullable=False, server_default="0"))
        if "valid_until_min" not in columns:
            batch_op.add_column(sa.Column("valid_until_min", sa.Float(), nullable=False, server_default="1440"))
        if "planned_departure_min" not in columns:
            batch_op.add_column(sa.Column("planned_departure_min", sa.Float(), nullable=False, server_default="0"))


def downgrade() -> None:
    raise RuntimeError("Route validity migration is non-destructive; use a disposable database to remove it.")
