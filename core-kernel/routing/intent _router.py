from rapidfuzz import fuzz


# threshold for considering a fuzzy-match 'confident'
CONFIDENCE_THRESHOLD = 50


def route_intent(text: str):
    """
    Cheap first-pass intent classifier.
    We'll upgrade to model-based routing later.
    """
    t = text.lower()

    booking_words = [
        "estimate",
        "appointment",
        "book",
        "schedule",
        "quote",
        "come look",
        "come out",
        "can you come check",
    ]
    faq_words = [
        "warranty",
        "leak",
        "soffit",
        "fascia",
        "hail",
        "insurance",
        "how long",
        "turnaround",
        "cleanup",
        "nails in yard",
    ]

    def score(words):
        return max(fuzz.partial_ratio(t, w) for w in words)

    booking_score = score(booking_words)
    faq_score = score(faq_words)

    if booking_score >= faq_score and booking_score > CONFIDENCE_THRESHOLD:
        return {"intent": "book_appointment", "confidence": booking_score / 100.0}

    if faq_score > CONFIDENCE_THRESHOLD:
        return {"intent": "faq", "confidence": faq_score / 100.0}

    return {"intent": "handoff", "confidence": 0.4}
