"""
Idempotent seed script example.
Assumes SQLAlchemy 2.x-style engine + models available.
"""
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg2://aether:aetherpass@localhost:5432/aetherlink")

# Example imports — adjust these to your project
# from pods.customer_ops.db import Base, get_engine  # if you have helpers
# from pods.customer_ops.models import User

def upsert_user(session: Session, email: str, name: str):
    from pods.customer_ops.models import User  # local import to avoid import cycles
    existing = session.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if existing:
        # update minimal fields safely
        changed = False
        if existing.name != name:
            existing.name = name
            changed = True
        if changed:
            print(f"↺ Updated user {email}")
        else:
            print(f"✓ User {email} already up-to-date")
        return existing
    u = User(email=email, name=name, is_active=True)
    session.add(u)
    print(f"+ Inserted user {email}")
    return u

def main():
    print("🌱 Seeding data...")
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    with Session(engine) as session:
        upsert_user(session, "admin@aetherlink.local", "Aether Admin")
        # Add more upserts here (features, roles, demo customers, etc.)
        session.commit()
    print("🌱 Seed done.")

if __name__ == "__main__":
    main()
