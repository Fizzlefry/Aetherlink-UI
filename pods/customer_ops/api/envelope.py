from typing import Any


def ok(request_id: str, data: dict[str, Any], intent: str | None = None, confidence: float | None = None) -> dict[str, Any]:
    resp = {"ok": True, "request_id": request_id, "data": data}
    if intent is not None:
        resp["intent"] = intent
    if confidence is not None:
        resp["confidence"] = confidence
    return resp


def err(request_id: str, message: str, code: str = "error", status: int = 400) -> dict[str, Any]:
    return {"ok": False, "request_id": request_id, "error": {"message": message, "code": code, "status": status}}
