"""
Kafka event producer for ApexFlow CRM.
Publishes domain events for leads, jobs, and appointments.
"""
import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, Optional

from kafka import KafkaProducer
from kafka.errors import KafkaError
from prometheus_client import Counter

logger = logging.getLogger(__name__)

# Prometheus metrics
events_published = Counter(
    "apexflow_events_published_total",
    "Number of domain events published by ApexFlow",
    ["event_type", "tenant_id", "status"],
)

# Kafka configuration
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
KAFKA_ENABLED = os.getenv("KAFKA_ENABLED", "true").lower() == "true"

# Initialize Kafka producer (lazy initialization)
_producer: Optional[KafkaProducer] = None


def get_producer() -> Optional[KafkaProducer]:
    """Get or create Kafka producer instance."""
    global _producer
    
    if not KAFKA_ENABLED:
        logger.info("Kafka is disabled (KAFKA_ENABLED=false)")
        return None
    
    if _producer is None:
        try:
            _producer = KafkaProducer(
                bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS.split(","),
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                key_serializer=lambda k: k.encode("utf-8") if k else None,
                acks="all",  # Wait for all replicas to acknowledge
                retries=3,
                max_in_flight_requests_per_connection=1,  # Maintain ordering
            )
            logger.info(f"Kafka producer initialized: {KAFKA_BOOTSTRAP_SERVERS}")
        except Exception as e:
            logger.error(f"Failed to initialize Kafka producer: {e}")
            return None
    
    return _producer


def _publish_event(
    topic: str,
    event_type: str,
    payload: Dict[str, Any],
    tenant_id: str,
    key: Optional[str] = None,
) -> bool:
    """
    Internal helper to publish an event to Kafka.
    
    Args:
        topic: Kafka topic name
        event_type: Event type for metrics (e.g., "lead.created")
        payload: Event payload dictionary
        tenant_id: Tenant ID for partitioning and metrics
        key: Optional message key for partitioning
    
    Returns:
        True if published successfully, False otherwise
    """
    producer = get_producer()
    
    if producer is None:
        logger.warning(f"Kafka producer not available, skipping event: {event_type}")
        events_published.labels(event_type=event_type, tenant_id=tenant_id, status="skipped").inc()
        return False
    
    try:
        # Add metadata
        payload["event_type"] = event_type
        payload["published_at"] = datetime.utcnow().isoformat()
        
        # Use tenant_id as key if not provided (ensures tenant ordering)
        message_key = key or tenant_id
        
        # Send to Kafka
        future = producer.send(topic, value=payload, key=message_key)
        
        # Wait for acknowledgment (with timeout)
        record_metadata = future.get(timeout=10)
        
        logger.info(
            f"Published {event_type} to {topic} "
            f"(partition={record_metadata.partition}, offset={record_metadata.offset})"
        )
        events_published.labels(event_type=event_type, tenant_id=tenant_id, status="success").inc()
        return True
        
    except KafkaError as e:
        logger.error(f"Kafka error publishing {event_type}: {e}")
        events_published.labels(event_type=event_type, tenant_id=tenant_id, status="error").inc()
        return False
    except Exception as e:
        logger.error(f"Unexpected error publishing {event_type}: {e}")
        events_published.labels(event_type=event_type, tenant_id=tenant_id, status="error").inc()
        return False


def publish_lead_created(lead: Any, tenant_id: str, actor: Optional[str] = None) -> bool:
    """
    Publish LeadCreated event with enhanced CRM fields.
    
    Args:
        lead: Lead database model instance
        tenant_id: Tenant ID
        actor: User who performed the action (from JWT preferred_username)
    
    Returns:
        True if published successfully
    """
    payload = {
        "id": lead.id,
        "tenant_id": tenant_id,
        "name": lead.name,
        "email": lead.email,
        "phone": lead.phone,
        "source": lead.source,
        "status": lead.status,
        "assigned_to": lead.assigned_to,
        "tags": lead.tags if hasattr(lead, 'tags') else [],
        "created_at": lead.created_at.isoformat() if lead.created_at else datetime.utcnow().isoformat(),
        "event_version": 1,
        "actor": actor,
    }
    
    return _publish_event(
        topic="apexflow.leads.created",
        event_type="lead.created",
        payload=payload,
        tenant_id=tenant_id,
        key=f"{tenant_id}:lead:{lead.id}",
    )


def publish_job_created(job: Any, tenant_id: str) -> bool:
    """
    Publish JobCreated event.
    
    Args:
        job: Job database model instance
        tenant_id: Tenant ID
    
    Returns:
        True if published successfully
    """
    payload = {
        "id": job.id,
        "tenant_id": tenant_id,
        "lead_id": job.lead_id,
        "title": job.title,
        "status": job.status,
        "description": job.description,
        "created_at": job.created_at.isoformat() if job.created_at else datetime.utcnow().isoformat(),
    }
    
    return _publish_event(
        topic="apexflow.jobs.created",
        event_type="job.created",
        payload=payload,
        tenant_id=tenant_id,
        key=f"{tenant_id}:job:{job.id}",
    )


def publish_lead_note_added(lead_id: int, note_id: int, body: str, author: str, tenant_id: str) -> bool:
    """
    Publish LeadNoteAdded event for activity timeline.
    
    Args:
        lead_id: Lead ID
        note_id: Note ID
        body: Note content
        author: Note author (from JWT)
        tenant_id: Tenant ID
    
    Returns:
        True if published successfully
    """
    payload = {
        "note_id": note_id,
        "lead_id": lead_id,
        "tenant_id": tenant_id,
        "body": body,
        "author": author,
        "event_version": 1,
        "created_at": datetime.utcnow().isoformat(),
    }
    
    return _publish_event(
        topic="apexflow.leads.note_added",
        event_type="lead.note_added",
        payload=payload,
        tenant_id=tenant_id,
        key=f"{tenant_id}:lead:{lead_id}",
    )


def publish_lead_status_changed(
    lead_id: int,
    old_status: str,
    new_status: str,
    actor: str,
    tenant_id: str
) -> bool:
    """
    Publish LeadStatusChanged event when a lead's status changes.
    
    Args:
        lead_id: Lead ID
        old_status: Previous status value
        new_status: New status value
        actor: User who made the change
        tenant_id: Tenant ID
    
    Returns:
        True if published successfully
    """
    payload = {
        "lead_id": lead_id,
        "tenant_id": tenant_id,
        "old_status": old_status,
        "new_status": new_status,
        "actor": actor,
        "event_version": 1,
        "changed_at": datetime.utcnow().isoformat(),
    }
    
    return _publish_event(
        topic="apexflow.leads.status_changed",
        event_type="lead.status_changed",
        payload=payload,
        tenant_id=tenant_id,
        key=f"{tenant_id}:lead:{lead_id}",
    )


def publish_lead_assigned(
    lead_id: int,
    assigned_to: str | None,
    actor: str,
    tenant_id: str
) -> bool:
    """
    Publish LeadAssigned event when a lead is assigned/reassigned.
    
    Args:
        lead_id: Lead ID
        assigned_to: User assigned to lead (or None if unassigned)
        actor: User who made the change
        tenant_id: Tenant ID
    
    Returns:
        True if published successfully
    """
    payload = {
        "lead_id": lead_id,
        "tenant_id": tenant_id,
        "assigned_to": assigned_to,
        "actor": actor,
        "event_version": 1,
        "assigned_at": datetime.utcnow().isoformat(),
    }
    
    return _publish_event(
        topic="apexflow.leads.assigned",
        event_type="lead.assigned",
        payload=payload,
        tenant_id=tenant_id,
        key=f"{tenant_id}:lead:{lead_id}",
    )


def publish_appointment_created(appointment: Any, tenant_id: str) -> bool:
    """
    Publish AppointmentCreated event.
    
    Args:
        appointment: Appointment database model instance
        tenant_id: Tenant ID
    
    Returns:
        True if published successfully
    """
    payload = {
        "id": appointment.id,
        "tenant_id": tenant_id,
        "lead_id": appointment.lead_id,
        "job_id": appointment.job_id,
        "scheduled_at": appointment.scheduled_at.isoformat() if appointment.scheduled_at else None,
        "type": appointment.type,
        "notes": appointment.notes,
        "created_at": datetime.utcnow().isoformat(),
    }
    
    return _publish_event(
        topic="apexflow.appointments.created",
        event_type="appointment.created",
        payload=payload,
        tenant_id=tenant_id,
        key=f"{tenant_id}:appointment:{appointment.id}",
    )


def close_producer():
    """Close Kafka producer connection (call on shutdown)."""
    global _producer
    if _producer is not None:
        try:
            _producer.flush()
            _producer.close()
            logger.info("Kafka producer closed")
        except Exception as e:
            logger.error(f"Error closing Kafka producer: {e}")
        finally:
            _producer = None
