from pydantic import BaseModel
from sqlalchemy import Column, DateTime, Integer, String, func
from sqlalchemy.orm import declarative_base

# SQLAlchemy models
Base = declarative_base()


class Lead(Base):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    intent = Column(String(50), nullable=True)  # e.g. "booking", "quote"
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# Pydantic models for API
class ChatRequest(BaseModel):
    user_id: str
    message: str


class FaqRequest(BaseModel):
    query: str


class FaqAnswer(BaseModel):
    answer: str
    citations: list[str]
    score: float


class ChatResponse(BaseModel):
    """Response for /chat endpoint"""

    reply: str  # The text response to send to the user
    intent: str  # "faq" | "booking" | "human"
    confidence: float  # 0-1 score of how confident we are in the intent
    lead_id: int  # ID of the lead record created for tracking
