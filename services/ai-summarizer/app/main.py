# services/ai-summarizer/app/main.py
import os
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

"""
AI Summarizer for AetherLink
- Fetches lead activity from ApexFlow
- Sends to Claude Sonnet (or other LLM) using a clean prompt
- Returns short, operator-friendly summary
"""

APEXFLOW_BASE = os.getenv("APEXFLOW_BASE", "http://apexflow:8080")
# Claude endpoint + key — you can swap to your gateway / proxy
CLAUDE_ENDPOINT = os.getenv("CLAUDE_ENDPOINT", "https://api.anthropic.com/v1/messages")
CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY", "")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-3-sonnet-20240229")


class ActivityItem(BaseModel):
    type: str
    actor: str | None = None
    at: str | None = None
    data: dict[str, Any] | None = None
    text: str | None = None
    is_system: bool | None = None


class SummaryResponse(BaseModel):
    lead_id: int
    tenant_id: str
    summary: str
    confidence: float = 0.85
    raw_tokens: int | None = None


app = FastAPI(
    title="AetherLink AI Summarizer",
    version="0.1.0",
    description="Summarizes lead activity using Claude Sonnet.",
)


def build_prompt(lead_id: int, tenant_id: str, activity: list[ActivityItem]) -> str:
    """
    Turn our normalized activity into a stable, LLM-friendly prompt.
    Keep it deterministic so UI can depend on it.
    """
    lines = [
        "You are an assistant for an event-driven CRM called AetherLink.",
        "You will be given the full activity history for a single lead.",
        "Return a short, operator-friendly summary that answers:",
        "1) what's going on with this lead,",
        "2) what changed most recently,",
        "3) what the next action should be (if obvious).",
        "",
        f"Lead ID: {lead_id}",
        f"Tenant: {tenant_id}",
        "",
        "Activity (newest first):",
    ]
    for item in activity:
        kind = item.type
        actor = item.actor or "unknown"
        when = item.at or "unknown time"

        if kind == "created":
            src = item.data.get("source") if item.data else None
            lines.append(f"- [{when}] CREATED by system from {src or 'unknown source'}")
        elif kind == "note":
            text = item.text or ""
            lines.append(f"- [{when}] NOTE by {actor}: {text}")
        elif kind == "assigned":
            assignee = item.data.get("assigned_to") if item.data else None
            lines.append(f"- [{when}] ASSIGNED by {actor} → {assignee}")
        elif kind == "status_changed":
            old_s = item.data.get("old_status") if item.data else "unknown"
            new_s = item.data.get("new_status") if item.data else "unknown"
            lines.append(f"- [{when}] STATUS by {actor}: {old_s} → {new_s}")
        else:
            # fallback
            lines.append(f"- [{when}] {kind} by {actor}")

    lines.append("")
    lines.append("Return JSON with keys: summary, next_action.")
    return "\n".join(lines)


async def call_claude(prompt: str) -> str:
    if not CLAUDE_API_KEY:
        # Dev mode: no external call
        return '{"summary": "No Claude API key configured. Here is the prompt you would have sent.", "next_action": "configure CLAUDE_API_KEY env var and retry."}'

    headers = {
        "x-api-key": CLAUDE_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {
        "model": CLAUDE_MODEL,
        "max_tokens": 400,
        "temperature": 0.4,
        "messages": [
            {
                "role": "user",
                "content": prompt,
            }
        ],
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(CLAUDE_ENDPOINT, headers=headers, json=payload)
        if resp.status_code >= 400:
            raise HTTPException(status_code=500, detail=f"Claude error: {resp.text}")
        data = resp.json()
        # Anthropic messages API returns content = [{type: "text", text: "..."}]
        content = data["content"][0]["text"]
        return content


@app.get("/health")
async def health():
    return {"status": "ok", "service": "aetherlink-ai-summarizer"}


class LeadExtractionRequest(BaseModel):
    tenant_id: str
    raw_text: str


class LeadExtractionResponse(BaseModel):
    name: str | None = None
    email: str | None = None
    company: str | None = None
    phone: str | None = None
    status: str | None = "new"
    tags: list[str] | None = None
    raw: dict[str, Any] | None = None


@app.post("/summaries/extract-lead", response_model=LeadExtractionResponse)
async def extract_lead(payload: LeadExtractionRequest):
    """
    Take unstructured text (email signature, LinkedIn scrape, meeting notes)
    and extract normalized lead fields for CRM.
    """
    # Stub mode - try naive extraction when no Claude key
    if not CLAUDE_API_KEY:
        guessed_email = None
        guessed_name = None

        # Super naive: find email using regex
        import re

        email_pattern = r"[\w\.-]+@[\w\.-]+"
        email_matches = re.findall(email_pattern, payload.raw_text)
        if email_matches:
            guessed_email = email_matches[0]

        # Try to guess name (first line that looks like a name)
        lines = payload.raw_text.strip().split("\n")
        if lines:
            first_line = lines[0].strip()
            # If first line is short and doesn't have @ or http, guess it's a name
            if len(first_line) < 50 and "@" not in first_line and "http" not in first_line:
                guessed_name = first_line

        return LeadExtractionResponse(
            name=guessed_name or "(unknown)",
            email=guessed_email,
            company=None,
            phone=None,
            status="new",
            tags=["ai-extracted", "stub-mode"],
            raw={"stub": True},
        )

    # Real Claude extraction
    prompt = f"""You are an assistant that extracts lead/contact data for a CRM.

Input text:
---
{payload.raw_text}
---

Extract the following fields and return ONLY valid JSON (no markdown, no explanation):
- name: person's full name (string or null)
- email: email address (string or null)
- company: company/organization name (string or null)
- phone: phone number (string or null)
- status: one of ["new","contacted","qualified","proposal","won","lost"], default "new"
- tags: array of relevant tags (e.g. ["inbound", "linkedin", "warm-lead"])

Return JSON with these exact keys. If a field is missing, use null."""

    headers = {
        "x-api-key": CLAUDE_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    payload_claude = {
        "model": CLAUDE_MODEL,
        "max_tokens": 256,
        "temperature": 0.3,
        "messages": [
            {
                "role": "user",
                "content": prompt,
            }
        ],
    }

    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post(CLAUDE_ENDPOINT, headers=headers, json=payload_claude)
        if resp.status_code >= 400:
            raise HTTPException(status_code=500, detail=f"Claude error: {resp.text}")
        data = resp.json()
        content = data["content"][0]["text"]

    # Parse Claude's JSON response
    import json

    try:
        parsed = json.loads(content)
    except Exception:
        # If Claude didn't return valid JSON, return minimal response
        parsed = {}

    return LeadExtractionResponse(
        name=parsed.get("name"),
        email=parsed.get("email"),
        company=parsed.get("company"),
        phone=parsed.get("phone"),
        status=parsed.get("status") or "new",
        tags=parsed.get("tags") or ["ai-extracted"],
        raw=parsed,
    )


@app.get("/summaries/lead/{lead_id}", response_model=SummaryResponse)
async def summarize_lead(
    lead_id: int,
    tenant_id: str = Query(..., description="Tenant to fetch under"),
):
    # 1) fetch activity from ApexFlow
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(
            f"{APEXFLOW_BASE}/leads/{lead_id}/activity",
            headers={"x-tenant-id": tenant_id},
        )
    if r.status_code == 404:
        raise HTTPException(status_code=404, detail="Lead not found")
    if r.status_code >= 400:
        raise HTTPException(status_code=500, detail="Failed to fetch activity")

    activity_raw = r.json()
    activity: list[ActivityItem] = [ActivityItem(**a) for a in activity_raw]

    # 2) build prompt
    prompt = build_prompt(lead_id, tenant_id, activity)

    # 3) call Claude
    claude_result = await call_claude(prompt)

    # We asked for JSON, but users / models sometimes reply with text;
    # we'll just return text straight for now.
    return SummaryResponse(
        lead_id=lead_id,
        tenant_id=tenant_id,
        summary=claude_result,
        confidence=0.85,
    )
