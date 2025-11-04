"""
Seed data for Sprint 0: demo org, admin user, roles, sample data.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from .auth import get_password_hash
from .auth_models import Org, Permission, Role, User, UserRole
from .db import SessionLocal
from .models_v2 import Job, Lead, Opportunity


def seed_database():
    """Create demo org, admin user, roles, and sample data."""
    db: Session = SessionLocal()

    try:
        # Check if org already exists
        existing_org = db.query(Org).first()
        if existing_org:
            print("✅ Database already seeded, skipping...")
            return

        print("🌱 Seeding database...")

        # Create demo org
        demo_org = Org(name="Demo Roofing Co", subdomain="demo", is_active=True)
        db.add(demo_org)
        db.flush()

        # Create admin user
        admin_user = User(
            org_id=demo_org.id,
            email="admin@peakpro.io",
            hashed_password=get_password_hash("admin123"),
            full_name="Admin User",
            is_active=True,
            is_superuser=True,
        )
        db.add(admin_user)
        db.flush()

        # Create roles
        admin_role = Role(org_id=demo_org.id, name="Admin", description="Full system access")
        sales_role = Role(
            org_id=demo_org.id, name="Sales", description="Lead and opportunity management"
        )
        ops_role = Role(
            org_id=demo_org.id, name="Operations", description="Job and crew management"
        )
        db.add_all([admin_role, sales_role, ops_role])
        db.flush()

        # Assign admin role
        admin_assignment = UserRole(user_id=admin_user.id, role_id=admin_role.id)
        db.add(admin_assignment)

        # Create permissions for admin role
        resources = ["leads", "opportunities", "jobs", "users", "roles"]
        actions = ["read", "write", "delete"]
        for resource in resources:
            for action in actions:
                perm = Permission(role_id=admin_role.id, resource=resource, action=action)
                db.add(perm)

        # Create sample leads
        leads_data = [
            {
                "name": "Smith Residence",
                "email": "john.smith@email.com",
                "phone": "555-0100",
                "company": "Smith Family",
                "source": "web",
                "status": "new",
                "score": 75,
                "heat_level": "hot",
                "notes": "Needs roof replacement after storm damage",
            },
            {
                "name": "Johnson Commercial",
                "email": "mary@johnson.biz",
                "phone": "555-0200",
                "company": "Johnson Enterprises",
                "source": "referral",
                "status": "contacted",
                "score": 60,
                "heat_level": "warm",
                "notes": "Commercial building, 20k sq ft flat roof",
            },
            {
                "name": "Brown Townhomes",
                "email": "info@browntownhomes.com",
                "phone": "555-0300",
                "company": "Brown Property Management",
                "source": "api",
                "status": "qualified",
                "score": 85,
                "heat_level": "hot",
                "notes": "Multi-unit complex, need quote by end of week",
            },
        ]

        created_leads = []
        for lead_data in leads_data:
            lead = Lead(org_id=demo_org.id, **lead_data)
            db.add(lead)
            created_leads.append(lead)

        db.flush()

        # Create opportunities from qualified leads
        qualified_lead = created_leads[2]  # Brown Townhomes
        opportunity = Opportunity(
            org_id=demo_org.id,
            lead_id=qualified_lead.id,
            stage="proposal",
            probability=0.7,
            value=125000.0,
            notes="Proposal sent, waiting for board approval",
        )
        db.add(opportunity)
        db.flush()

        # Create sample jobs
        jobs_data = [
            {
                "name": "Davis Roof Replacement",
                "site_address": "123 Main St, Springfield, IL 62701",
                "status": "in_progress",
                "start_date": datetime.now(UTC) - timedelta(days=2),
                "end_date": datetime.now(UTC) + timedelta(days=5),
                "crew_id": 1,
                "notes": "Asphalt shingles, 25-year warranty",
            },
            {
                "name": "Wilson Garage Repair",
                "site_address": "456 Oak Ave, Springfield, IL 62702",
                "status": "scheduled",
                "start_date": datetime.now(UTC) + timedelta(days=7),
                "end_date": datetime.now(UTC) + timedelta(days=8),
                "crew_id": 2,
                "notes": "Minor leak repair, inspect flashing",
            },
        ]

        for job_data in jobs_data:
            job = Job(org_id=demo_org.id, opportunity_id=None, **job_data)
            db.add(job)

        # Commit all changes
        db.commit()

        print("✅ Database seeded successfully!")
        print("   📧 Admin login: admin@peakpro.io / admin123")
        print(f"   🏢 Org: {demo_org.name} (ID: {demo_org.id})")
        print("   👤 Users: 1")
        print(f"   🎯 Leads: {len(created_leads)}")
        print("   💼 Opportunities: 1")
        print(f"   🔨 Jobs: {len(jobs_data)}")

    except Exception as e:
        db.rollback()
        print(f"❌ Error seeding database: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
