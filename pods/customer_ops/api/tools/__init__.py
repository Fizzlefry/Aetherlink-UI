from .lead_lookup import lead_lookup, LeadLookupInput
from .schedule_inspection import schedule_inspection, ScheduleInspectionInput

# JSON-schema like specs for LLMs
TOOLS = [
    {
        "name": "lead_lookup",
        "description": "Fetch a lead by id and return structured information.",
        "input_schema": {
            "type": "object",
            "properties": {"lead_id": {"type": "string"}},
            "required": ["lead_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "schedule_inspection",
        "description": "Schedule an inspection for a job on a specific date (YYYY-MM-DD).",
        "input_schema": {
            "type": "object",
            "properties": {
                "job_id": {"type": "string"},
                "date": {"type": "string", "description": "YYYY-MM-DD"},
            },
            "required": ["job_id", "date"],
            "additionalProperties": False,
        },
    },
]

# Name -> callable resolver
TOOL_FUNCS = {
    "lead_lookup": lead_lookup,
    "schedule_inspection": schedule_inspection,
}
