from crm import models_v2 as models
from crm import schemas
from crm.auth_routes import get_current_user
from crm.db import get_db
from crm.scoring import score_lead
from fastapi import APIRouter, Depends, HTTPException
from prometheus_client import Counter
from sqlalchemy.orm import Session

router = APIRouter()

# Prometheus metrics
leads_created_total = Counter("crm_leads_created_total", "Total leads created", ["source"])


# Lead endpoints
@router.post("/leads", response_model=schemas.Lead, status_code=201)
def create_lead(
    lead: schemas.LeadCreate, db: Session = Depends(get_db), user=Depends(get_current_user)
):
    """Create a new lead."""
    db_lead = models.Lead(**lead.model_dump(), org_id=user.org_id)

    # Calculate score and heat level
    db_lead.score, db_lead.heat_level = score_lead(db_lead)

    db.add(db_lead)
    db.commit()
    db.refresh(db_lead)

    # Increment Prometheus counter
    leads_created_total.labels(source=lead.source).inc()

    return db_lead


@router.get("/leads", response_model=list[schemas.Lead])
def list_leads(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """List all leads."""
    leads = db.query(models.Lead).offset(skip).limit(limit).all()
    return leads


@router.get("/leads/{lead_id}", response_model=schemas.Lead)
def get_lead(lead_id: int, db: Session = Depends(get_db)):
    """Get a specific lead."""
    lead = db.query(models.Lead).filter(models.Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return lead


# Project endpoints
@router.post("/projects", response_model=schemas.Project, status_code=201)
def create_project(project: schemas.ProjectCreate, db: Session = Depends(get_db)):
    """Create a new project."""
    db_project = models.Project(**project.model_dump())
    db.add(db_project)
    db.commit()
    db.refresh(db_project)
    return db_project


@router.get("/projects", response_model=list[schemas.Project])
def list_projects(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """List all projects."""
    projects = db.query(models.Project).offset(skip).limit(limit).all()
    return projects


# Contact endpoints
@router.post("/contacts", response_model=schemas.Contact, status_code=201)
def create_contact(contact: schemas.ContactCreate, db: Session = Depends(get_db)):
    """Create a new contact."""
    db_contact = models.Contact(**contact.model_dump())
    db.add(db_contact)
    db.commit()
    db.refresh(db_contact)
    return db_contact


@router.get("/contacts", response_model=list[schemas.Contact])
def list_contacts(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """List all contacts."""
    contacts = db.query(models.Contact).offset(skip).limit(limit).all()
    return contacts
