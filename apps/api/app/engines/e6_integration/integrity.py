from typing import Optional

from sqlalchemy.orm import Session

from app.models.entities import StateSnapshot


class SnapshotIntegrityError(ValueError):
    """Raised when an output crosses snapshot or immutability boundaries."""


class SnapshotIntegrity:
    """Small, reusable guard layer for cross-engine snapshot invariants."""

    @staticmethod
    def require_snapshot(db: Session, snapshot_id: str) -> StateSnapshot:
        snapshot = db.query(StateSnapshot).filter(StateSnapshot.id == snapshot_id).first()
        if not snapshot:
            raise SnapshotIntegrityError(f"SNAPSHOT_NOT_FOUND: '{snapshot_id}'")
        return snapshot

    @classmethod
    def require_mutable_snapshot(cls, db: Session, snapshot_id: str) -> StateSnapshot:
        snapshot = cls.require_snapshot(db, snapshot_id)
        if snapshot.is_immutable or snapshot.snapshot_type == "BASELINE" or snapshot.id == "SNAP_BASE_001":
            raise SnapshotIntegrityError(f"SNAPSHOT_IMMUTABLE: '{snapshot_id}'")
        return snapshot

    @staticmethod
    def require_same_snapshot(expected_snapshot_id: str, actual_snapshot_id: Optional[str], entity_name: str) -> None:
        if actual_snapshot_id != expected_snapshot_id:
            raise SnapshotIntegrityError(
                f"SNAPSHOT_MISMATCH: {entity_name} belongs to '{actual_snapshot_id}', "
                f"expected '{expected_snapshot_id}'"
            )
