from typing import Literal

from fastapi import Depends, FastAPI
from pydantic import BaseModel
from sqlalchemy.orm import Session

from . import observability
from .crud import create_lead
from .deps import get_db
from .handlers.chat_handler import handle_chat
from .models import Base
from .session import engine


# Make sure tables exist in the database at startup
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="CustomerOps Pod API",
    description="AI Customer Service Pod for The Expert Co. (AetherLink prototype)",
    version="0.1.0",
)

# Initialize observability (logging, metrics, readiness)
observability.init(app)


class ChatRequest(BaseModel):
    text: str
    channel: Literal["sms", "voice", "web"] = "web"
    phone: str | None = None


class ChatResponse(BaseModel):
    reply: str
    intent: str
    confidence: float


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/chat", response_model=ChatResponse)
def chat_endpoint(payload: ChatRequest, db: Session = Depends(get_db)):
    """
    Main chat entry point:
    - Classifies intent
    - Generates reply text
    - If it's a "book" intent, store/reuse a lead record in DB
    """

    result = handle_chat(payload.model_dump(), settings={})

    # If user wants to book, capture their info as a lead
    if result["intent"] == "book":
        create_lead(
            db=db,
            name=None,
            phone=payload.phone,
            intent=result["intent"],
        )
    return {
        "reply": result["reply"],
        "intent": result["intent"],
        "confidence": result["confidence"],
    }
