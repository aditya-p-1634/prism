"""PRISM V2 — Evacuation State Machine (E5)
==============================================
Distinguishes Planning Allocations from Operational Evacuation Lifecycle States.

CORE PRINCIPLE:
PLAN != STATE
- RelocationAllocation represents PRISM's planning recommendation (status: RECOMMENDED, OVERRIDDEN, etc.)
- EvacuationState represents the actual real-world operational execution lifecycle of the relocated group.

CANONICAL LIFECYCLE:
    PLANNED -> NOTIFIED -> ACKNOWLEDGED -> EVACUATION_ORDERED -> MOVING -> IN_TRANSIT -> ARRIVED -> SHELTERED

OPERATIONAL EXCEPTION STATES (NON-TERMINAL):
    - NO_RESPONSE: No confirmation received following notification.
    - ROUTE_BLOCKED: Route degraded/blocked during movement; recoverable when rerouted.
    - STUCK: Vehicle or group immobilized in transit; recoverable after field assistance.
    - REQUIRES_ASSISTANCE: Special mobility/medical/logistical support required.
"""

from typing import Set, Dict, List, Optional, Any
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.entities import RelocationAllocation, RelocationGroup, Habitation, Destination, StateSnapshot, AuditEvent, User
from app.models.enums import EvacuationStateEnum, RoleEnum


VALID_TRANSITIONS: Dict[EvacuationStateEnum, Set[EvacuationStateEnum]] = {
    # 1. Canonical Normal Lifecycle Progression
    EvacuationStateEnum.PLANNED: {
        EvacuationStateEnum.NOTIFIED,
    },
    EvacuationStateEnum.NOTIFIED: {
        EvacuationStateEnum.ACKNOWLEDGED,
        EvacuationStateEnum.NO_RESPONSE,
        EvacuationStateEnum.REQUIRES_ASSISTANCE,
    },
    EvacuationStateEnum.ACKNOWLEDGED: {
        EvacuationStateEnum.EVACUATION_ORDERED,
        EvacuationStateEnum.REQUIRES_ASSISTANCE,
    },
    EvacuationStateEnum.EVACUATION_ORDERED: {
        EvacuationStateEnum.MOVING,
        EvacuationStateEnum.ROUTE_BLOCKED,
        EvacuationStateEnum.REQUIRES_ASSISTANCE,
    },
    EvacuationStateEnum.MOVING: {
        EvacuationStateEnum.IN_TRANSIT,
        EvacuationStateEnum.ROUTE_BLOCKED,
        EvacuationStateEnum.STUCK,
        EvacuationStateEnum.REQUIRES_ASSISTANCE,
    },
    EvacuationStateEnum.IN_TRANSIT: {
        EvacuationStateEnum.ARRIVED,
        EvacuationStateEnum.ROUTE_BLOCKED,
        EvacuationStateEnum.STUCK,
        EvacuationStateEnum.REQUIRES_ASSISTANCE,
    },
    EvacuationStateEnum.ARRIVED: {
        EvacuationStateEnum.SHELTERED,
        EvacuationStateEnum.REQUIRES_ASSISTANCE,
    },
    EvacuationStateEnum.SHELTERED: {
        # Sheltered is terminal unless emergency welfare or secondary transfer is needed
        EvacuationStateEnum.REQUIRES_ASSISTANCE,
    },

    # 2. Operational Exception Recovery Transitions (NON-TERMINAL)
    EvacuationStateEnum.NO_RESPONSE: {
        EvacuationStateEnum.NOTIFIED,          # Re-notification attempt
        EvacuationStateEnum.EVACUATION_ORDERED, # Mandatory/forced evacuation order by authority
        EvacuationStateEnum.REQUIRES_ASSISTANCE,# Search and rescue / welfare dispatch
    },
    EvacuationStateEnum.ROUTE_BLOCKED: {
        EvacuationStateEnum.IN_TRANSIT,        # Resumes transit on rerouted viable bypass
        EvacuationStateEnum.MOVING,            # Resumes movement
        EvacuationStateEnum.STUCK,             # Immobilized after all reroutes fail
        EvacuationStateEnum.REQUIRES_ASSISTANCE,# Emergency road rescue / clearance needed
    },
    EvacuationStateEnum.STUCK: {
        EvacuationStateEnum.IN_TRANSIT,        # Resumes transit after vehicle towing or clearance
        EvacuationStateEnum.MOVING,            # Resumes local detour movement
        EvacuationStateEnum.REQUIRES_ASSISTANCE,# Specialized rescue dispatch
        EvacuationStateEnum.ARRIVED,           # Arrived if assisted right at perimeter
    },
    EvacuationStateEnum.REQUIRES_ASSISTANCE: {
        EvacuationStateEnum.MOVING,            # Assisted movement begins
        EvacuationStateEnum.IN_TRANSIT,        # Evacuation continues in emergency transit
        EvacuationStateEnum.ARRIVED,           # Direct arrival at destination via emergency transport
        EvacuationStateEnum.SHELTERED,         # Direct admission to shelter medical/care facility
    },
}


class EvacuationStateMachine:
    """Centralized domain service governing evacuation lifecycle state transitions."""

    @staticmethod
    def can_transition(from_state: EvacuationStateEnum, to_state: EvacuationStateEnum) -> bool:
        """Determines whether a transition from from_state to to_state is valid."""
        if from_state == to_state:
            return False
        allowed = VALID_TRANSITIONS.get(from_state, set())
        return to_state in allowed

    @staticmethod
    def get_allowed_transitions(current_state: EvacuationStateEnum) -> List[EvacuationStateEnum]:
        """Returns the list of allowed destination states from current_state."""
        return sorted(list(VALID_TRANSITIONS.get(current_state, set())), key=lambda s: s.value)

    @classmethod
    def transition_state(
        cls,
        db: Session,
        allocation_id: str,
        to_state: EvacuationStateEnum,
        justification: str,
        current_user: Optional[User] = None,
        expected_current_state: Optional[EvacuationStateEnum] = None
    ) -> RelocationAllocation:
        """
        Atomically executes an evacuation state transition on an allocation record.
        Enforces:
        - Allocation existence
        - Snapshot baseline immutability (SNAP_BASE_001 cannot undergo operational state mutation)
        - Valid transition policy
        - Concurrency / stale state verification
        - Atomic transaction with rollback
        - Tamper-evident AuditEvent creation
        """
        # 1. Justification validation
        if not justification or len(justification.strip()) < 5:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="INVALID_TRANSITION_PAYLOAD: Operational justification is required and must be at least 5 characters."
            )

        # 2. Lookup allocation
        alloc = db.query(RelocationAllocation).filter(RelocationAllocation.id == allocation_id).first()
        if not alloc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"ALLOCATION_NOT_FOUND: Relocation allocation '{allocation_id}' not found."
            )

        # 3. Snapshot Baseline Immutability Check (Invariant 6)
        snapshot = db.query(StateSnapshot).filter(StateSnapshot.id == alloc.snapshot_id).first()
        if not snapshot:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"SNAPSHOT_NOT_FOUND: State snapshot '{alloc.snapshot_id}' not found."
            )

        if snapshot.is_immutable or snapshot.id == "SNAP_BASE_001":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"BASELINE_IMMUTABLE: Canonical baseline snapshot '{snapshot.id}' is immutable. "
                       "Operational evacuation states cannot be transitioned against the baseline snapshot. "
                       "Execute a scenario branch first."
            )

        # 4. Concurrency / Stale State Check
        current_state = alloc.evacuation_state
        if expected_current_state is not None and current_state != expected_current_state:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"STALE_STATE_CONFLICT: Allocation state has changed from '{expected_current_state.value}' to '{current_state.value}'. "
                       "Please refresh before attempting transition."
            )

        # 5. Transition Graph Validation
        if not cls.can_transition(current_state, to_state):
            allowed = [s.value for s in cls.get_allowed_transitions(current_state)]
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"INVALID_STATE_TRANSITION: Cannot transition evacuation state from '{current_state.value}' to '{to_state.value}'. "
                       f"Allowed transitions from '{current_state.value}': {allowed}."
            )

        # 6. Lookup group and habitation context for audit trail
        group = db.query(RelocationGroup).filter(RelocationGroup.id == alloc.group_id).first()
        hab = db.query(Habitation).filter(Habitation.id == group.habitation_id).first() if group else None
        dest = db.query(Destination).filter(Destination.id == alloc.destination_id).first() if alloc.destination_id else None

        before_state = {
            "snapshot_id": alloc.snapshot_id,
            "allocation_id": alloc.id,
            "group_id": alloc.group_id,
            "origin_habitation": hab.code if hab else None,
            "destination_code": dest.code if dest else None,
            "allocation_status": alloc.allocation_status.value if hasattr(alloc.allocation_status, 'value') else str(alloc.allocation_status),
            "evacuation_state": current_state.value if hasattr(current_state, 'value') else str(current_state),
            "assigned_capacity_count": alloc.assigned_capacity_count,
        }

        # 7. Apply state mutation
        alloc.evacuation_state = to_state

        after_state = {
            "snapshot_id": alloc.snapshot_id,
            "allocation_id": alloc.id,
            "group_id": alloc.group_id,
            "origin_habitation": hab.code if hab else None,
            "destination_code": dest.code if dest else None,
            "allocation_status": alloc.allocation_status.value if hasattr(alloc.allocation_status, 'value') else str(alloc.allocation_status),
            "evacuation_state": to_state.value if hasattr(to_state, 'value') else str(to_state),
            "assigned_capacity_count": alloc.assigned_capacity_count,
        }

        # 8. Record append-only audit trail
        audit = AuditEvent(
            user_id=current_user.id if current_user else None,
            action_type="EVACUATION_STATE_TRANSITION",
            entity_type="RelocationAllocation",
            entity_id=alloc.id,
            before_state=before_state,
            after_state=after_state,
            justification=justification.strip()
        )
        db.add(audit)

        # 9. Atomic commit
        try:
            db.commit()
            db.refresh(alloc)
        except Exception as e:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"TRANSACTION_FAILED: Failed to atomically commit evacuation state transition: {str(e)}"
            )

        return alloc
