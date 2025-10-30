import models  # models.py is in the same folder
from sqlalchemy.orm import Session


def create_lead(
    db: Session,
    name: str | None = None,
    phone: str | None = None,
    intent: str | None = None,
):
    lead = models.Lead(
        name=name,
        phone=phone,
        intent=intent,
    )

    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead
