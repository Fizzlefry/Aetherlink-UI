# pods/customer-ops/api/handlers/chat_handler.py

# temporary intent router (stub)
def route_intent(message: str) -> str:
    msg = message.lower()

    if "book" in msg or "appointment" in msg or "schedule" in msg:
        return "booking"

    if "price" in msg or "how much" in msg or "do you offer" in msg or "what do you do" in msg:
        return "faq"

    return "agent"  # fallback to human / escalation


def handle_chat(payload, settings):
    """
    payload: ChatRequest (text, channel, phone)
    settings: placeholder for config/env if we need it

    returns dict like:
    {
        "reply": "...",
        "intent": "faq" | "booking" | "agent",
        "confidence": 0.7
    }
    """

    user_message = payload.text
    intent = route_intent(user_message)

    if intent == "booking":
        reply = (
            "Got it, you want to book. "
            "We can get you on the schedule. Which works better for you: "
            "tomorrow morning or tomorrow afternoon?"
        )
        confidence = 0.8

    elif intent == "faq":
        reply = (
            "Sure. We offer professional cleaning services. "
            "Pricing depends on the job size — would you like a quick quote?"
        )
        confidence = 0.8

    else:
        # 'agent' fallback
        reply = "Thanks for reaching out. I'll hand you to a specialist so we can help personally."
        confidence = 0.6

    return {
        "reply": reply,
        "intent": intent,
        "confidence": confidence,
    }
