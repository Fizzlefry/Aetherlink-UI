def handle_faq(user_text: str, settings) -> str:
    """
    For now, this is your voice.
    We'll replace with RAG later.
    Edit this content to match how you talk to homeowners.
    """

    canned_answers = [
        ("We can usually get someone out within 1-2 business days, " "depending on your location."),
        (
            "For hail or storm damage, we take photos and document everything "
            "to help you with insurance."
        ),
        (
            "On fascia/soffit work we can usually match color, or re-wrap in "
            "new aluminum if it's too far gone."
        ),
        "Every job includes cleanup. We run magnets for nails and haul away debris.",
    ]

    base = (
        "Here's how we normally handle this: "
        f"{canned_answers[0]} "
        "Would you like to get on the schedule?"
    )

    return base
