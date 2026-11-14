"""Create the initial PRISM schema.

This is a transitional baseline migration. It delegates table creation to the
authoritative SQLAlchemy metadata while the existing prototype schema is being
captured. Future revisions must use explicit Alembic operations and must not
drop production data in a downgrade.
"""

from alembic import op

from app.db.session import Base
import app.models  # noqa: F401 - register all SQLAlchemy models


revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    raise RuntimeError(
        "The PRISM baseline migration is intentionally non-destructive. "
        "Use a disposable database when testing schema removal."
    )
