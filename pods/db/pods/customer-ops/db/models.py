from sqlalchemy import Column, DateTime, Integer, String, func
from sqlalchemy.orm import declarative_base


Base = declarative_base()


class Lead(Base):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    intent = Column(String(50), nullable=True)  # e.g. "booking", "quote"
    created_at = Column(DateTime(timezone=True), server_default=func.now())
