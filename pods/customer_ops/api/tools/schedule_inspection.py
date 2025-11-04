from datetime import datetime
from typing import TypedDict


class ScheduleInspectionInput(TypedDict):
    job_id: str
    date: str  # YYYY-MM-DD


async def schedule_inspection(args: ScheduleInspectionInput) -> dict:
    # Validate date
    try:
        when = datetime.strptime(args["date"], "%Y-%m-%d").date()
    except Exception as e:
        return {"ok": False, "error": f"Invalid date: {e}"}
    # TODO: integrate calendar/vendor; this is a safe stub
    return {
        "ok": True,
        "job_id": args["job_id"],
        "date": str(when),
        "confirmation": "INSPECT-TEST-123",
    }
