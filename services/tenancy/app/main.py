"""
Aetherlink Tenancy Service
- Tenant management
- PostgreSQL storage
- Prometheus metrics
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy import create_engine, text
import os
from prometheus_client import generate_latest

# Database configuration
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://tenancy:tenancy@tenancy_db:5432/tenancy"
)

# Create SQLAlchemy engine
engine = create_engine(DATABASE_URL, future=True)

# FastAPI app
app = FastAPI(
    title="Aetherlink Tenancy Service",
    version="1.0.0",
    description="Multi-tenant management service"
)


@app.on_event("startup")
def initialize_database():
    """Create tables on startup"""
    with engine.begin() as connection:
        connection.execute(text("""
            CREATE TABLE IF NOT EXISTS tenants (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                slug TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """))
        
        connection.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_tenants_slug ON tenants(slug);
        """))


@app.get("/healthz", tags=["Health"])
def health_check():
    """Health check endpoint"""
    return {"ok": True}


@app.get("/metrics", tags=["Metrics"])
def metrics():
    """Prometheus metrics endpoint"""
    return generate_latest()


class TenantInput(BaseModel):
    """Tenant creation input"""
    slug: str
    name: str


class TenantOutput(BaseModel):
    """Tenant output"""
    id: str
    slug: str
    name: str


@app.post("/tenants", tags=["Tenants"], response_model=dict)
def create_tenant(tenant: TenantInput):
    """
    Create a new tenant
    
    Args:
        tenant: Tenant information (slug, name)
    
    Returns:
        Success status and tenant slug
    """
    try:
        with engine.begin() as connection:
            connection.execute(
                text("INSERT INTO tenants(slug, name) VALUES(:slug, :name)"),
                {"slug": tenant.slug, "name": tenant.name}
            )
        return {"ok": True, "slug": tenant.slug}
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to create tenant: {str(e)}"
        )


@app.get("/tenants", tags=["Tenants"])
def list_tenants():
    """
    List all tenants
    
    Returns:
        List of tenants with id, slug, name
    """
    with engine.connect() as connection:
        result = connection.execute(
            text("SELECT id::text, slug, name FROM tenants ORDER BY slug")
        )
        rows = result.mappings().all()
    
    return {"items": list(rows)}


@app.get("/tenants/{slug}", tags=["Tenants"])
def get_tenant(slug: str):
    """
    Get tenant by slug
    
    Args:
        slug: Tenant slug identifier
    
    Returns:
        Tenant information
    """
    with engine.connect() as connection:
        result = connection.execute(
            text("SELECT id::text, slug, name FROM tenants WHERE slug = :slug"),
            {"slug": slug}
        )
        row = result.mappings().first()
    
    if not row:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    return dict(row)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
