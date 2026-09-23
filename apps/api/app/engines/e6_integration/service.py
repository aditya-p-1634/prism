import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from app.models.entities import StateSnapshot, Event, EventDelivery, Job, AuditEvent, User
from app.models.enums import JobStatusEnum

class IntegrationBackboneE6:
    """Engine 6: Data/GIS/System Integration Backbone."""

    def __init__(self, db: Session):
        self.db = db

    def create_snapshot(
        self,
        label: str,
        snapshot_type: str = "BASELINE",
        scenario_id: Optional[str] = None,
        is_immutable: bool = False
    ) -> StateSnapshot:
        snapshot = StateSnapshot(
            scenario_id=scenario_id,
            snapshot_type=snapshot_type,
            label=label,
            is_immutable=is_immutable
        )
        self.db.add(snapshot)
        self.db.commit()
        self.db.refresh(snapshot)
        return snapshot

    def get_snapshot(self, snapshot_id: str) -> Optional[StateSnapshot]:
        return self.db.query(StateSnapshot).filter(StateSnapshot.id == snapshot_id).first()

    def publish_event(self, event_type: str, payload: Dict[str, Any], consumers: List[str]) -> Event:
        event = Event(
            event_type=event_type,
            payload=payload
        )
        self.db.add(event)
        self.db.flush()

        for consumer in consumers:
            delivery = EventDelivery(
                event_id=event.id,
                consumer_engine=consumer,
                is_delivered=True,
                delivered_at=datetime.now(timezone.utc)
            )
            self.db.add(delivery)

        self.db.commit()
        return event

    def create_job(self, job_type: str, input_payload: Dict[str, Any]) -> Job:
        job = Job(
            job_type=job_type,
            status=JobStatusEnum.PENDING,
            progress_pct=0,
            input_payload=input_payload
        )
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job

    def update_job(
        self,
        job_id: str,
        status: JobStatusEnum,
        progress_pct: int = 100,
        result_payload: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None
    ) -> Job:
        job = self.db.query(Job).filter(Job.id == job_id).first()
        if job:
            job.status = status
            job.progress_pct = progress_pct
            if result_payload:
                job.result_payload = result_payload
            if error_message:
                job.error_message = error_message
            self.db.commit()
            self.db.refresh(job)
        return job

    def record_audit_event(
        self,
        action_type: str,
        entity_type: str,
        entity_id: str,
        justification: str,
        user_id: Optional[str] = None,
        before_state: Optional[Dict[str, Any]] = None,
        after_state: Optional[Dict[str, Any]] = None
    ) -> AuditEvent:
        audit = AuditEvent(
            user_id=user_id,
            action_type=action_type,
            entity_type=entity_type,
            entity_id=entity_id,
            before_state=before_state or {},
            after_state=after_state or {},
            justification=justification
        )
        self.db.add(audit)
        self.db.commit()
        self.db.refresh(audit)
        return audit
