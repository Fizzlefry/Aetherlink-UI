def handle_booking(payload, settings) -> str:
    """
    For now, offer two time windows.
    Later, we'll integrate live Google Calendar.
    We'll also start asking name, address, and callback number.
    """

    return (
        "We can get you on the schedule. Which works better for you: "
        "tomorrow at 10am, or tomorrow at 2pm?"
    )
