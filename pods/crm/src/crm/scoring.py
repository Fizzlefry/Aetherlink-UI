"""
Lead scoring service - rules-based + heat level calculation.
"""

from datetime import UTC, datetime


def score_lead(lead) -> tuple[int, str]:
    """
    Calculate lead score and heat level based on multiple factors.

    Returns:
        Tuple of (score: int, heat_level: str)
    """
    score = 0

    # Source weight (referrals are hottest)
    source_weights = {"referral": 30, "web": 20, "partner": 25, "api": 10, "cold_call": 5}
    score += source_weights.get(lead.source or "", 5)

    # Contact completeness (more info = more serious)
    if lead.phone:
        score += 10
    if lead.email and any(
        lead.email.endswith(domain) for domain in [".com", ".net", ".org", ".biz"]
    ):
        score += 5
    if lead.company:
        score += 5

    # Recency (newer leads are hotter)
    if hasattr(lead, "created_at") and lead.created_at:
        age_hours = (datetime.now(UTC) - lead.created_at).total_seconds() / 3600
        if age_hours < 24:
            score += 20
        elif age_hours < 72:
            score += 10
        elif age_hours < 168:  # 1 week
            score += 5

    # Status progression
    status_bonus = {"qualified": 15, "contacted": 10, "meeting_scheduled": 20, "proposal_sent": 25}
    score += status_bonus.get(lead.status or "new", 0)

    # Heat level mapping
    if score >= 70:
        heat = "hot"
    elif score >= 40:
        heat = "warm"
    else:
        heat = "cold"

    return score, heat
