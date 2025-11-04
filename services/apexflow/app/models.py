# PeakPro AI CRM - Database Models
# Internal codename: apexflow
from datetime import datetime
from typing import List
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import String, Integer, DateTime, ForeignKey, Index, text, Boolean, JSON

class Base(DeclarativeBase):
    pass

class TenantScoped:
    """Mixin for multi-tenant tables"""
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

class Lead(Base, TenantScoped):
    """Lead entity - represents potential customers"""
    __tablename__ = "leads"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=True)
    phone: Mapped[str] = mapped_column(String(32), nullable=True)
    email: Mapped[str] = mapped_column(String(160), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    
    # CRM lifecycle fields
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="new")
    assigned_to: Mapped[str | None] = mapped_column(String(160), nullable=True)
    tags: Mapped[List[str]] = mapped_column(JSON, nullable=False, server_default="[]")
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    
    # Relationships
    jobs: Mapped[list["Job"]] = relationship("Job", back_populates="lead", cascade="all, delete-orphan")
    appointments: Mapped[list["Appointment"]] = relationship("Appointment", back_populates="lead", cascade="all, delete-orphan")

    __table_args__ = (
        # Unique email per tenant (allows NULL)
        Index("ix_leads_tenant_email_unique", "tenant_id", "email", unique=True, 
              postgresql_where=text("email IS NOT NULL")),
        # Phone lookup per tenant
        Index("ix_leads_tenant_phone", "tenant_id", "phone"),
        # Common queries
        Index("ix_leads_tenant_created", "tenant_id", "created_at"),
        # CRM lifecycle indexes (created by migration)
        # ix_leads_status, ix_leads_assigned_to, ix_leads_is_archived, ix_leads_tenant_status
    )

class Job(Base, TenantScoped):
    """Job entity - work orders derived from leads"""
    __tablename__ = "jobs"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(String(48), nullable=False, server_default="Pending")
    description: Mapped[str] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"), 
                                                   onupdate=datetime.utcnow)
    
    # Relationships
    lead: Mapped["Lead"] = relationship("Lead", back_populates="jobs")

    __table_args__ = (
        # Status filtering per tenant
        Index("ix_jobs_tenant_status", "tenant_id", "status"),
        # Lead lookup
        Index("ix_jobs_tenant_lead", "tenant_id", "lead_id"),
    )

class Appointment(Base, TenantScoped):
    """Appointment entity - scheduled events for jobs"""
    __tablename__ = "appointments"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True, index=True)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    type: Mapped[str] = mapped_column(String(64), nullable=True)
    notes: Mapped[str] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    
    # Relationships
    lead: Mapped["Lead"] = relationship("Lead", back_populates="appointments")

    __table_args__ = (
        # Time-range queries per tenant
        Index("ix_appt_tenant_scheduled", "tenant_id", "scheduled_at"),
        # Lead appointment lookup
        Index("ix_appt_tenant_lead", "tenant_id", "lead_id"),
    )

class LeadNote(Base, TenantScoped):
    """Note/comment on a lead - for activity timeline and collaboration"""
    __tablename__ = "lead_notes"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id", ondelete="CASCADE"), nullable=False)
    body: Mapped[str] = mapped_column(String, nullable=False)  # Text type
    author: Mapped[str] = mapped_column(String(160), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"), nullable=False)
    
    __table_args__ = (
        # Efficient tenant+lead queries ordered by time
        Index("ix_lead_notes_lead_tenant", "tenant_id", "lead_id", "created_at"),
    )
