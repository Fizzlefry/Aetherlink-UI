"""
Updated CRM models with multi-tenancy, opportunities, and jobs.
"""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Float, Text, Boolean, JSON, func
from pgvector.sqlalchemy import Vector
from .db import Base


class Lead(Base):
    """Lead/prospect model with multi-tenancy."""
    __tablename__ = "leads"
    
    id = Column(Integer, primary_key=True, index=True)
    org_id = Column(Integer, ForeignKey("orgs.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False)
    phone = Column(String(50))
    company = Column(String(255))
    source = Column(String(100))
    status = Column(String(50), default="new")
    notes = Column(Text)
    
    # New fields for AI scoring
    score = Column(Integer, default=0)
    heat_level = Column(String(20), default="cold")  # cold, warm, hot
    converted_at = Column(DateTime, nullable=True)
    
    # Sprint 5: QuickBooks Online invoice tracking
    qbo_invoice_id = Column(String(64), index=True)
    qbo_invoice_number = Column(String(64))
    qbo_status = Column(String(24))  # "Paid", "Open", "Unknown"
    qbo_balance_cents = Column(Integer)
    qbo_paid_cents = Column(Integer)
    qbo_last_sync_at = Column(DateTime(timezone=True))
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class Opportunity(Base):
    """Opportunity (qualified lead moving through sales pipeline)."""
    __tablename__ = "opportunities"
    
    id = Column(Integer, primary_key=True, index=True)
    org_id = Column(Integer, ForeignKey("orgs.id"), nullable=False, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=False, index=True)
    stage = Column(String(50), default="qualification")  # qualification, proposal, negotiation, closed_won, closed_lost
    probability = Column(Float, default=0.0)  # 0.0 to 1.0
    value = Column(Float, default=0.0)  # Estimated deal value
    notes = Column(Text)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class Job(Base):
    """Job/project (work to be executed)."""
    __tablename__ = "jobs"
    
    id = Column(Integer, primary_key=True, index=True)
    org_id = Column(Integer, ForeignKey("orgs.id"), nullable=False, index=True)
    opportunity_id = Column(Integer, ForeignKey("opportunities.id"), nullable=True, index=True)
    
    name = Column(String(255), nullable=False)
    site_address = Column(Text)
    status = Column(String(50), default="scheduled")  # scheduled, in_progress, completed, cancelled
    
    # Scheduling
    start_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)
    crew_id = Column(Integer, nullable=True)  # FK to crews table (future)
    
    # Notes with vector embedding for semantic search
    notes = Column(Text)
    notes_embedding = Column(Vector(1536), nullable=True)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class Attachment(Base):
    """File attachment with vector embedding."""
    __tablename__ = "attachments"
    
    id = Column(Integer, primary_key=True, index=True)
    org_id = Column(Integer, ForeignKey("orgs.id"), nullable=False, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=True, index=True)
    
    filename = Column(String(255), nullable=False)
    key = Column(String(500), nullable=False)  # S3/MinIO key
    url = Column(String(500))  # Presigned URL (short-lived)
    content_type = Column(String(100))
    size_bytes = Column(Integer)
    
    # Vector embedding for semantic search over images/docs
    embedding = Column(Vector(1536), nullable=True)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Project(Base):
    """Legacy project model (will merge with Job)."""
    __tablename__ = "projects"
    
    id = Column(Integer, primary_key=True, index=True)
    org_id = Column(Integer, ForeignKey("orgs.id"), nullable=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    status = Column(String(50), default="active")
    budget = Column(Float)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class Contact(Base):
    """Legacy contact model."""
    __tablename__ = "contacts"
    
    id = Column(Integer, primary_key=True, index=True)
    org_id = Column(Integer, ForeignKey("orgs.id"), nullable=True, index=True)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    email = Column(String(255))
    phone = Column(String(50))
    company = Column(String(255))
    role = Column(String(100))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class Customer(Base):
    """Customer record for portal access."""
    __tablename__ = "customers"
    
    id = Column(Integer, primary_key=True)
    org_id = Column(Integer, index=True, nullable=False)
    email = Column(String(320), unique=True, nullable=False)
    full_name = Column(String(200))
    phone = Column(String(50))
    is_active = Column(Boolean, server_default="true")
    created_at = Column(DateTime, server_default=func.now())
    
    # Sprint 5: QuickBooks Online sync
    qbo_customer_id = Column(String(64), index=True)
    qbo_last_sync_at = Column(DateTime(timezone=True))


class PortalActivity(Base):
    """Activity log for portal events."""
    __tablename__ = "portal_activity_log"
    
    id = Column(Integer, primary_key=True)
    org_id = Column(Integer, index=True, nullable=False)
    customer_id = Column(Integer, nullable=False)
    proposal_id = Column(Integer)
    event = Column(String(50), nullable=False)  # view|approve|download|email_sent
    meta = Column(JSON)
    created_at = Column(DateTime, server_default=func.now())
