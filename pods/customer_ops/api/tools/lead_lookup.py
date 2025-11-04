from typing import TypedDict


class LeadLookupInput(TypedDict):
    lead_id: str


async def lead_lookup(args: LeadLookupInput) -> dict:
    # TODO: wire to real datastore/CRM; this is a safe stub
    lead_id = args["lead_id"]
    return {
        "lead_id": lead_id,
        "name": "Sample Lead",
        "email": "lead@example.com",
        "status": "open",
        "notes": "Stubbed lead; connect to real DB later.",
    }
