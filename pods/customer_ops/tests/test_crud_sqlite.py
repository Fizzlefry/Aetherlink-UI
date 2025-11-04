import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from pods.customer_ops.api import crud as api_crud
from pods.customer_ops.api import models as api_models


@pytest.fixture
def in_memory_db():
    engine = create_engine("sqlite:///:memory:")
    session_local = sessionmaker(bind=engine)
    api_models.Base.metadata.create_all(bind=engine)
    return session_local


def test_create_lead(in_memory_db):
    db = in_memory_db()
    lead = api_crud.create_lead(db=db, name="Test User", phone="12345", intent="book")
    assert lead.id is not None
    assert lead.name == "Test User"
    assert lead.phone == "12345"
    assert lead.intent == "book"

    # cleanup
    db.close()
