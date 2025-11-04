# pods/customer_ops/api/enrich.py
from __future__ import annotations

_POS = {"great", "thanks", "love", "awesome", "perfect"}
_NEG = {"angry", "frustrated", "mad", "upset", "problem", "issue", "late"}
_URG = {"urgent", "asap", "today", "now", "emergency", "leak", "active leak"}
_INTENT = {
    "lead_capture": {"quote", "estimate", "bid", "price", "schedule", "book"},
    "support": {"warranty", "repair", "leak", "problem", "issue"},
    "info": {"question", "info", "information", "details"},
}


def _contains(text: str, bag: set[str]) -> bool:
    t = text.lower()
    return any(w in t for w in bag)


def enrich_text(text: str) -> dict[str, str | float]:
    # intent
    intent = "lead_capture"
    best = 0
    for name, bag in _INTENT.items():
        score = sum(1 for w in bag if w in text.lower())
        if score > best:
            best = score
            intent = name

    # sentiment
    if _contains(text, _POS) and not _contains(text, _NEG):
        sentiment = "positive"
    elif _contains(text, _NEG) and not _contains(text, _POS):
        sentiment = "negative"
    else:
        sentiment = "neutral"

    # urgency
    urgency = "high" if _contains(text, _URG) else "normal"

    # naive score (baseline)
    score = 0.7 if intent == "lead_capture" else 0.5
    if urgency == "high":
        score += 0.1
    if sentiment == "negative":
        score -= 0.1
    return {
        "intent": intent,
        "sentiment": sentiment,
        "urgency": urgency,
        "score": max(0.0, min(1.0, score)),
    }
