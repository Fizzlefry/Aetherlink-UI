from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


# Lead Schemas
class LeadBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr | None = None
    phone: str | None = Field(None, max_length=50)
    company: str | None = Field(None, max_length=255)
    source: str = Field(default="api", max_length=50)
    status: str = Field(default="new", max_length=50)
    notes: str | None = None


class LeadCreate(LeadBase):
    pass


class LeadUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    email: EmailStr | None = None
    phone: str | None = Field(None, max_length=50)
    company: str | None = Field(None, max_length=255)
    source: str | None = Field(None, max_length=50)
    status: str | None = Field(None, max_length=50)
    notes: str | None = None


class Lead(LeadBase):
    id: int
    score: int = 0
    heat_level: str = "cold"
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Project Schemas
class ProjectBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    status: str = Field(default="planning", max_length=50)
    budget: int | None = Field(None, ge=0)


class ProjectCreate(ProjectBase):
    pass


class Project(ProjectBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Contact Schemas
class ContactBase(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    phone: str | None = Field(None, max_length=50)
    company: str | None = Field(None, max_length=255)
    role: str | None = Field(None, max_length=100)


class ContactCreate(ContactBase):
    pass


class Contact(ContactBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Customer Schemas (Sprint 2)
class CustomerCreate(BaseModel):
    email: EmailStr
    full_name: str | None = None
    phone: str | None = None


class CustomerOut(BaseModel):
    id: int
    email: EmailStr
    full_name: str | None
    phone: str | None

    class Config:
        from_attributes = True
