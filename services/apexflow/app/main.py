from fastapi import FastAPI, Depends, Header, HTTPException
from fastapi.responses import PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import IntegrityError
from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List
import os

from .models import Base, Lead, Job, Appointment, LeadNote

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://postgres:postgres@db-apexflow:5432/apexflow")
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

# FastAPI app
app = FastAPI(
    title="AetherLink CRM",
    version="1.2.0",
    description="Lead → Job → Appointment workflow engine (powered by ApexFlow)"
)

# CORS for UI development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Metrics
REQS = Counter("apexflow_requests_total", "Total requests", ["path", "method", "tenant"])
LEADS_ASSIGNED = Counter("apexflow_leads_assigned_total", "Total lead assignments", ["tenant_id", "actor"])

# Database dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_tenant(
    x_tenant_id: str = Header(default=None),
    x_jwt_tenant: str = Header(default=None, alias="x-jwt-tenant-id")
) -> str:
    """
    Extract and validate tenant ID from request header and JWT claims.
    Enforces tenant consistency to prevent header spoofing.
    """
    if not x_tenant_id and not x_jwt_tenant:
        raise HTTPException(status_code=400, detail="tenant required (x-tenant-id header or JWT claim)")
    
    # If both present, they must match
    if x_tenant_id and x_jwt_tenant and x_tenant_id != x_jwt_tenant:
        raise HTTPException(
            status_code=403, 
            detail=f"tenant mismatch: header='{x_tenant_id}' jwt='{x_jwt_tenant}'"
        )
    
    # Prefer JWT tenant (most trustworthy), fallback to header
    return x_jwt_tenant or x_tenant_id

def get_user() -> dict:
    """
    Validate JWT token and extract user identity.
    In production, this should verify JWT signature via Keycloak public key.
    For MVP, we trust the Gateway's validation.
    """
    return {"sub": "admin", "roles": ["admin"]}

# Pydantic schemas for request/response
class LeadCreate(BaseModel):
    name: str
    source: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    status: Optional[str] = "new"
    assigned_to: Optional[str] = None
    tags: Optional[list[str]] = []

class LeadUpdate(BaseModel):
    """Schema for PATCH /leads/{id} - all fields optional"""
    name: Optional[str] = None
    source: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    status: Optional[str] = None
    assigned_to: Optional[str] = None
    tags: Optional[list[str]] = None
    is_archived: Optional[bool] = None

class LeadResponse(BaseModel):
    id: int
    tenant_id: str
    name: str
    source: Optional[str]
    phone: Optional[str]
    email: Optional[str]
    created_at: datetime
    status: str
    assigned_to: Optional[str]
    tags: list[str]
    is_archived: bool

    class Config:
        from_attributes = True

class LeadNoteCreate(BaseModel):
    body: str

class LeadNoteResponse(BaseModel):
    id: int
    lead_id: int
    body: str
    author: str
    created_at: datetime

    class Config:
        from_attributes = True

class JobCreate(BaseModel):
    lead_id: int
    title: str
    status: str = "Pending"
    description: Optional[str] = None

class JobResponse(BaseModel):
    id: int
    tenant_id: str
    lead_id: int
    title: str
    status: str
    description: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True

class AppointmentCreate(BaseModel):
    lead_id: int
    job_id: Optional[int] = None
    scheduled_at: datetime
    type: Optional[str] = None
    notes: Optional[str] = None

class AppointmentResponse(BaseModel):
    id: int
    tenant_id: str
    lead_id: int
    job_id: Optional[int]
    scheduled_at: datetime
    type: Optional[str]
    notes: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True

class ActivityItem(BaseModel):
    """Unified activity timeline item"""
    type: str  # "note", "assigned", "status_changed", "created"
    actor: str
    at: datetime
    data: dict
    is_system: bool = False  # True for auto-generated activities

# === Health & Metrics Endpoints ===

@app.get("/healthz", response_class=PlainTextResponse)
def healthz():
    """Health check endpoint - always returns OK if service is running"""
    return "ok"

@app.get("/readyz", response_class=PlainTextResponse)
def readyz():
    """Readiness check - returns OK when service can handle requests"""
    return "ready"

@app.get("/metrics")
def metrics():
    """Prometheus metrics endpoint"""
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)

# === Lead Endpoints ===

@app.post("/leads", tags=["Leads"], response_model=LeadResponse)
def create_lead(
    payload: LeadCreate,
    db: Session = Depends(get_db),
    tenant: str = Depends(get_tenant),
    user: dict = Depends(get_user)
):
    """Create a new lead"""
    REQS.labels("/leads", "POST", tenant).inc()
    
    lead = Lead(
        tenant_id=tenant,
        name=payload.name,
        source=payload.source,
        phone=payload.phone,
        email=payload.email,
        status=payload.status or "new",
        assigned_to=payload.assigned_to,
        tags=payload.tags or []
    )
    
    try:
        db.add(lead)
        db.commit()
        db.refresh(lead)
        
        # Emit domain event
        from .kafka import publish_lead_created
        actor = user.get("preferred_username", "unknown") if user else "system"
        publish_lead_created(lead, tenant_id=tenant, actor=actor)
        
        return lead
    except IntegrityError as e:
        db.rollback()
        if "ix_leads_tenant_email_unique" in str(e):
            raise HTTPException(status_code=409, detail=f"Lead with email {payload.email} already exists")
        raise HTTPException(status_code=400, detail="Database constraint violation")

class LeadListResponse(BaseModel):
    items: list[LeadResponse]
    total: int
    limit: int
    offset: int

# Valid fields for ordering
VALID_ORDER_FIELDS = {
    "created_at": Lead.created_at,
    "name": Lead.name,
    "status": Lead.status,
    "email": Lead.email,
}

@app.get("/leads", tags=["Leads"], response_model=LeadListResponse)
def list_leads(
    status: Optional[str] = None,
    assigned_to: Optional[str] = None,
    q: Optional[str] = None,
    archived: Optional[bool] = False,
    limit: int = 50,
    offset: int = 0,
    order_by: str = "created_at",
    order: str = "desc",
    db: Session = Depends(get_db),
    tenant: str = Depends(get_tenant),
    user: dict = Depends(get_user)
):
    """
    List leads for the current tenant with pagination and filtering.
    
    - **status**: Filter by lead status (new, contacted, qualified, proposal, won, lost)
    - **assigned_to**: Filter by assigned user. Use special value `UNASSIGNED` to query leads with no assignment (assigned_to IS NULL)
    - **q**: Search by name, email, or phone (partial match)
    - **archived**: Include archived leads (default: false)
    - **limit**: Results per page (default: 50, max: 200)
    - **offset**: Pagination offset (default: 0)
    - **order_by**: Sort field (created_at, name, status, email)
    - **order**: Sort direction (asc, desc)
    
    **Examples:**
    - `GET /leads?assigned_to=UNASSIGNED` → returns unassigned leads
    - `GET /leads?assigned_to=sarah@acme.com` → returns leads assigned to sarah@acme.com
    """
    REQS.labels("/leads", "GET", tenant).inc()
    
    # Start with tenant filter
    query = db.query(Lead).filter(Lead.tenant_id == tenant)
    count_query = db.query(Lead).filter(Lead.tenant_id == tenant)
    
    # Apply filters to both queries
    if status:
        query = query.filter(Lead.status == status)
        count_query = count_query.filter(Lead.status == status)
    if assigned_to:
        # Special sentinel value "UNASSIGNED" maps to IS NULL filter
        if assigned_to == "UNASSIGNED":
            query = query.filter(Lead.assigned_to.is_(None))
            count_query = count_query.filter(Lead.assigned_to.is_(None))
        else:
            query = query.filter(Lead.assigned_to == assigned_to)
            count_query = count_query.filter(Lead.assigned_to == assigned_to)
    if not archived:
        query = query.filter(Lead.is_archived == False)
        count_query = count_query.filter(Lead.is_archived == False)
    
    # Search filter (name, email, or phone contains query string)
    if q:
        search_term = f"%{q}%"
        search_filter = (
            (Lead.name.ilike(search_term)) |
            (Lead.email.ilike(search_term)) |
            (Lead.phone.ilike(search_term))
        )
        query = query.filter(search_filter)
        count_query = count_query.filter(search_filter)
    
    # Get total count before pagination
    total = count_query.count()
    
    # Apply ordering
    order_col = VALID_ORDER_FIELDS.get(order_by, Lead.created_at)
    if order.lower() == "asc":
        query = query.order_by(order_col.asc())
    else:
        query = query.order_by(order_col.desc())
    
    # Apply pagination
    capped_limit = min(limit, 200)
    query = query.limit(capped_limit).offset(offset)
    
    leads = query.all()
    
    return {
        "items": leads,
        "total": total,
        "limit": capped_limit,
        "offset": offset,
    }

@app.get("/leads/{lead_id}", tags=["Leads"], response_model=LeadResponse)
def get_lead(
    lead_id: int,
    db: Session = Depends(get_db),
    tenant: str = Depends(get_tenant),
    user: dict = Depends(get_user)
):
    """Get a specific lead by ID"""
    REQS.labels("/leads/{id}", "GET", tenant).inc()
    lead = db.query(Lead).filter(Lead.id == lead_id, Lead.tenant_id == tenant).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return lead

class Owner(BaseModel):
    email: str
    name: str

@app.get("/owners", tags=["Leads"], response_model=list[Owner])
def list_owners(
    tenant: str = Depends(get_tenant),
    user: dict = Depends(get_user)
):
    """
    Get list of available lead owners for assignment.
    Later this will be backed by a users/owners table per tenant.
    For now, returns a static list per tenant.
    """
    REQS.labels("/owners", "GET", tenant).inc()
    
    # Static owner list - later replace with DB query
    # TODO: SELECT email, name FROM crm_owners WHERE tenant_id = ?
    return [
        {"email": "sarah@acme.com", "name": "Sarah Johnson"},
        {"email": "ops@acme.com", "name": "Ops Team"},
        {"email": "sales@acme.com", "name": "Sales Queue"},
    ]

@app.patch("/leads/{lead_id}", tags=["Leads"], response_model=LeadResponse)
def update_lead(
    lead_id: int,
    payload: LeadUpdate,
    db: Session = Depends(get_db),
    tenant: str = Depends(get_tenant),
    user: dict = Depends(get_user)
):
    """Update a lead (partial update) - emits granular change events"""
    REQS.labels("/leads/{id}", "PATCH", tenant).inc()
    
    lead = db.query(Lead).filter(Lead.id == lead_id, Lead.tenant_id == tenant).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    # Validate status if provided
    valid_statuses = ["new", "contacted", "qualified", "proposal", "won", "lost"]
    if payload.status and payload.status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}")
    
    # Track changes for granular events
    actor = user.get("preferred_username", "unknown") if user else "system"
    old_status = lead.status
    old_assigned_to = lead.assigned_to
    
    # Update only provided fields
    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(lead, field, value)
    
    try:
        db.commit()
        db.refresh(lead)
        
        # Emit granular change events
        from .kafka import publish_lead_status_changed, publish_lead_assigned
        
        if payload.status and payload.status != old_status:
            publish_lead_status_changed(
                lead_id=lead.id,
                old_status=old_status,
                new_status=payload.status,
                actor=actor,
                tenant_id=tenant
            )
            
            # Create system note for status change
            status_note = LeadNote(
                tenant_id=tenant,
                lead_id=lead.id,
                body=f"📊 Status changed: {old_status} → {payload.status}",
                author=actor
            )
            db.add(status_note)
            db.commit()
        
        if payload.assigned_to is not None and payload.assigned_to != old_assigned_to:
            publish_lead_assigned(
                lead_id=lead.id,
                assigned_to=payload.assigned_to,
                actor=actor,
                tenant_id=tenant
            )
            # Track assignment metrics
            LEADS_ASSIGNED.labels(tenant_id=tenant, actor=actor).inc()
            
            # Create system note for assignment change
            if payload.assigned_to and old_assigned_to:
                note_body = f"🔄 Reassigned from {old_assigned_to} to {payload.assigned_to}"
            elif payload.assigned_to:
                note_body = f"✅ Assigned to {payload.assigned_to}"
            else:
                note_body = f"❌ Unassigned (was {old_assigned_to})"
            
            system_note = LeadNote(
                tenant_id=tenant,
                lead_id=lead.id,
                body=note_body,
                author=actor
            )
            db.add(system_note)
            db.commit()
        
        return lead
    except IntegrityError as e:
        db.rollback()
        if "ix_leads_tenant_email_unique" in str(e):
            raise HTTPException(status_code=409, detail=f"Lead with email {payload.email} already exists")
        raise HTTPException(status_code=400, detail="Database constraint violation")

# === Job Endpoints ===

@app.post("/jobs", tags=["Jobs"], response_model=JobResponse)
def create_job(
    payload: JobCreate,
    db: Session = Depends(get_db),
    tenant: str = Depends(get_tenant),
    user: dict = Depends(get_user)
):
    """Create a new job"""
    REQS.labels("/jobs", "POST", tenant).inc()
    
    # Verify lead exists and belongs to tenant
    lead = db.query(Lead).filter(Lead.id == payload.lead_id, Lead.tenant_id == tenant).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    job = Job(
        tenant_id=tenant,
        lead_id=payload.lead_id,
        title=payload.title,
        status=payload.status,
        description=payload.description
    )
    
    db.add(job)
    db.commit()
    db.refresh(job)
    
    # Emit domain event
    from .kafka import publish_job_created
    publish_job_created(job, tenant_id=tenant)
    
    return job

@app.get("/jobs", tags=["Jobs"], response_model=List[JobResponse])
def list_jobs(
    db: Session = Depends(get_db),
    tenant: str = Depends(get_tenant),
    user: dict = Depends(get_user)
):
    """List all jobs for the current tenant"""
    REQS.labels("/jobs", "GET", tenant).inc()
    jobs = db.query(Job).filter(Job.tenant_id == tenant).order_by(Job.created_at.desc()).all()
    return jobs

@app.get("/jobs/{job_id}", tags=["Jobs"], response_model=JobResponse)
def get_job(
    job_id: int,
    db: Session = Depends(get_db),
    tenant: str = Depends(get_tenant),
    user: dict = Depends(get_user)
):
    """Get a specific job by ID"""
    REQS.labels("/jobs/{id}", "GET", tenant).inc()
    job = db.query(Job).filter(Job.id == job_id, Job.tenant_id == tenant).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

# === Appointment Endpoints ===

@app.post("/appointments", tags=["Appointments"], response_model=AppointmentResponse)
def create_appt(
    payload: AppointmentCreate,
    db: Session = Depends(get_db),
    tenant: str = Depends(get_tenant),
    user: dict = Depends(get_user)
):
    """Create a new appointment"""
    REQS.labels("/appointments", "POST", tenant).inc()
    
    # Verify lead exists and belongs to tenant
    lead = db.query(Lead).filter(Lead.id == payload.lead_id, Lead.tenant_id == tenant).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    # Verify job exists if provided
    if payload.job_id:
        job = db.query(Job).filter(Job.id == payload.job_id, Lead.tenant_id == tenant).first()
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
    
    appt = Appointment(
        tenant_id=tenant,
        lead_id=payload.lead_id,
        job_id=payload.job_id,
        scheduled_at=payload.scheduled_at,
        type=payload.type,
        notes=payload.notes
    )
    
    db.add(appt)
    db.commit()
    db.refresh(appt)
    return appt

@app.get("/appointments", tags=["Appointments"], response_model=List[AppointmentResponse])
def list_appts(
    db: Session = Depends(get_db),
    tenant: str = Depends(get_tenant),
    user: dict = Depends(get_user)
):
    """List all appointments for the current tenant"""
    REQS.labels("/appointments", "GET", tenant).inc()
    appts = db.query(Appointment).filter(Appointment.tenant_id == tenant).order_by(Appointment.scheduled_at.desc()).all()
    return appts

@app.get("/appointments/{appt_id}", tags=["Appointments"], response_model=AppointmentResponse)
def get_appt(
    appt_id: int,
    db: Session = Depends(get_db),
    tenant: str = Depends(get_tenant),
    user: dict = Depends(get_user)
):
    """Get a specific appointment by ID"""
    REQS.labels("/appointments/{id}", "GET", tenant).inc()
    appt = db.query(Appointment).filter(Appointment.id == appt_id, Appointment.tenant_id == tenant).first()
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")
    return appt

# === Lead Notes Endpoints ===

@app.post("/leads/{lead_id}/notes", tags=["Leads"], response_model=LeadNoteResponse)
def create_lead_note(
    lead_id: int,
    note: LeadNoteCreate,
    db: Session = Depends(get_db),
    tenant: str = Depends(get_tenant),
    user: dict = Depends(get_user)
):
    """
    Add a note/comment to a lead for activity timeline and collaboration.
    Publishes lead.note_added event to Kafka.
    """
    REQS.labels("/leads/{id}/notes", "POST", tenant).inc()
    
    # Ensure lead exists for tenant
    lead = db.query(Lead).filter(Lead.id == lead_id, Lead.tenant_id == tenant).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    # Extract actor from JWT
    actor = user.get("preferred_username", "unknown") if user else "system"
    
    # Create note
    db_note = LeadNote(
        tenant_id=tenant,
        lead_id=lead_id,
        body=note.body,
        author=actor,
    )
    db.add(db_note)
    db.commit()
    db.refresh(db_note)
    
    # Publish event: lead.note_added
    from .kafka import publish_lead_note_added
    publish_lead_note_added(
        lead_id=lead_id,
        note_id=db_note.id,
        body=note.body,
        author=actor,
        tenant_id=tenant
    )
    
    return db_note

@app.get("/leads/{lead_id}/notes", tags=["Leads"], response_model=list[LeadNoteResponse])
def list_lead_notes(
    lead_id: int,
    db: Session = Depends(get_db),
    tenant: str = Depends(get_tenant),
    user: dict = Depends(get_user)
):
    """Get all notes for a lead, ordered by newest first"""
    REQS.labels("/leads/{id}/notes", "GET", tenant).inc()
    
    # Ensure lead exists for tenant
    lead = db.query(Lead).filter(Lead.id == lead_id, Lead.tenant_id == tenant).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    notes = (
        db.query(LeadNote)
        .filter(LeadNote.tenant_id == tenant, LeadNote.lead_id == lead_id)
        .order_by(LeadNote.created_at.desc())
        .all()
    )
    return notes

@app.get("/leads/{lead_id}/activity", tags=["Leads"], response_model=list[ActivityItem])
def get_lead_activity(
    lead_id: int,
    db: Session = Depends(get_db),
    tenant: str = Depends(get_tenant),
    user: dict = Depends(get_user)
):
    """
    Get unified activity timeline for a lead.
    Returns all notes, assignments, status changes, and creation event in chronological order.
    """
    REQS.labels("/leads/{id}/activity", "GET", tenant).inc()
    
    # Ensure lead exists for tenant
    lead = db.query(Lead).filter(Lead.id == lead_id, Lead.tenant_id == tenant).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    activities = []
    
    # Add lead creation event
    activities.append(ActivityItem(
        type="created",
        actor="system",
        at=lead.created_at,
        data={"lead_id": lead.id, "name": lead.name, "source": lead.source or "unknown"},
        is_system=True
    ))
    
    # Add all notes (user-generated and system-generated)
    notes = (
        db.query(LeadNote)
        .filter(LeadNote.tenant_id == tenant, LeadNote.lead_id == lead_id)
        .all()
    )
    
    for note in notes:
        # Detect system-generated notes by emoji markers
        is_system = note.body.startswith(("✅", "🔄", "❌", "📊", "🎯"))
        
        # Parse assignment notes into structured data
        if note.body.startswith("✅ Assigned to "):
            assigned_to = note.body.replace("✅ Assigned to ", "").strip()
            activities.append(ActivityItem(
                type="assigned",
                actor=note.author,
                at=note.created_at,
                data={"assigned_to": assigned_to, "from": None},
                is_system=True
            ))
        elif note.body.startswith("🔄 Reassigned from "):
            parts = note.body.replace("🔄 Reassigned from ", "").split(" to ")
            if len(parts) == 2:
                activities.append(ActivityItem(
                    type="assigned",
                    actor=note.author,
                    at=note.created_at,
                    data={"assigned_to": parts[1].strip(), "from": parts[0].strip()},
                    is_system=True
                ))
        elif note.body.startswith("❌ Unassigned"):
            activities.append(ActivityItem(
                type="assigned",
                actor=note.author,
                at=note.created_at,
                data={"assigned_to": None, "from": note.body.split("(was ")[-1].rstrip(")")},
                is_system=True
            ))
        elif note.body.startswith("📊 Status changed: "):
            # Parse status change: "📊 Status changed: new → contacted"
            status_part = note.body.replace("📊 Status changed: ", "").strip()
            if " → " in status_part:
                old_status, new_status = status_part.split(" → ", 1)
                activities.append(ActivityItem(
                    type="status_changed",
                    actor=note.author,
                    at=note.created_at,
                    data={"old_status": old_status.strip(), "new_status": new_status.strip()},
                    is_system=True
                ))
            else:
                # Fallback if format doesn't match
                activities.append(ActivityItem(
                    type="note",
                    actor=note.author,
                    at=note.created_at,
                    data={"body": note.body, "note_id": note.id},
                    is_system=True
                ))
        else:
            # Regular note (user-generated or other system note)
            activities.append(ActivityItem(
                type="note",
                actor=note.author,
                at=note.created_at,
                data={"body": note.body, "note_id": note.id},
                is_system=is_system
            ))
    
    # Sort by timestamp descending (newest first)
    activities.sort(key=lambda x: x.at, reverse=True)
    
    return activities

# === Root Endpoint ===

@app.get("/", tags=["Info"])
def root():
    """API information"""
    return {
        "service": "AetherLink CRM",
        "version": "1.3.0",
        "engine": "ApexFlow",
        "status": "online"
    }
