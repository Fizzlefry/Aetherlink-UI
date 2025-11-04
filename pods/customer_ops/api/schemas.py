from typing import Literal

from pydantic import BaseModel, Field

# Lead outcome types for tracking conversion funnel
OutcomeType = Literal["booked", "ghosted", "qualified", "unqualified", "nurture", "spam"]


class LeadRequest(BaseModel):
    name: str = Field(..., min_length=2)
    phone: str = Field(..., min_length=7)
    details: str = Field("", max_length=2000)


class LeadResponse(BaseModel):
    lead_id: str


class LeadItem(BaseModel):
    id: str
    name: str
    phone: str
    details: str = ""
    tenant: str
    created_at: int
    intent: str | None = None
    sentiment: str | None = None
    urgency: str | None = None
    score: float | None = None
    last_messages: list[dict] = Field(default_factory=list)


class LeadListResponse(BaseModel):
    items: list[LeadItem]


class OutcomeRequest(BaseModel):
    """Record the outcome of a lead (for reward model training)."""

    outcome: OutcomeType
    notes: str = Field("", max_length=500)
    # Optional: time to conversion in seconds (for analytics)
    time_to_conversion: int | None = None


class OutcomeResponse(BaseModel):
    """Response after recording an outcome."""

    lead_id: str
    outcome: OutcomeType
    recorded_at: int


class OutcomeItem(BaseModel):
    """Individual outcome record with metadata."""

    lead_id: str
    outcome: OutcomeType
    notes: str
    recorded_at: int
    time_to_conversion: int | None = None


class AnalyticsResponse(BaseModel):
    """Aggregated outcome analytics."""

    total_leads: int
    total_outcomes: int
    conversion_rate: float  # booked / total_outcomes
    outcome_breakdown: dict[str, int]  # {"booked": 10, "ghosted": 5, ...}
    avg_time_to_conversion: float | None = None  # seconds
