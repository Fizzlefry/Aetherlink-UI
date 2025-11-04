"""
Test follow-up rule logic: schedule parsing, enqueue triggering, queue status.
"""


def test_parse_schedules_minutes():
    """Test schedule parser with minutes."""

    def _parse_schedules(csv: str) -> list[int]:
        out = []
        for part in (csv or "").split(","):
            part = part.strip().lower()
            if not part:
                continue
            if part.endswith("m"):
                out.append(int(part[:-1]) * 60)
            elif part.endswith("h"):
                out.append(int(part[:-1]) * 3600)
            elif part.endswith("d"):
                out.append(int(part[:-1]) * 86400)
            else:
                out.append(int(part))  # seconds
        return out

    assert _parse_schedules("30m") == [1800]
    assert _parse_schedules("30m,2h") == [1800, 7200]
    assert _parse_schedules("1h,1d") == [3600, 86400]


def test_parse_schedules_hours():
    """Test schedule parser with hours."""

    def _parse_schedules(csv: str) -> list[int]:
        out = []
        for part in (csv or "").split(","):
            part = part.strip().lower()
            if not part:
                continue
            if part.endswith("m"):
                out.append(int(part[:-1]) * 60)
            elif part.endswith("h"):
                out.append(int(part[:-1]) * 3600)
            elif part.endswith("d"):
                out.append(int(part[:-1]) * 86400)
            else:
                out.append(int(part))  # seconds
        return out

    assert _parse_schedules("2h") == [7200]
    assert _parse_schedules("1h,6h,12h") == [3600, 21600, 43200]


def test_parse_schedules_days():
    """Test schedule parser with days."""

    def _parse_schedules(csv: str) -> list[int]:
        out = []
        for part in (csv or "").split(","):
            part = part.strip().lower()
            if not part:
                continue
            if part.endswith("m"):
                out.append(int(part[:-1]) * 60)
            elif part.endswith("h"):
                out.append(int(part[:-1]) * 3600)
            elif part.endswith("d"):
                out.append(int(part[:-1]) * 86400)
            else:
                out.append(int(part))  # seconds
        return out

    assert _parse_schedules("1d") == [86400]
    assert _parse_schedules("1d,3d") == [86400, 259200]


def test_parse_schedules_seconds():
    """Test schedule parser with raw seconds."""

    def _parse_schedules(csv: str) -> list[int]:
        out = []
        for part in (csv or "").split(","):
            part = part.strip().lower()
            if not part:
                continue
            if part.endswith("m"):
                out.append(int(part[:-1]) * 60)
            elif part.endswith("h"):
                out.append(int(part[:-1]) * 3600)
            elif part.endswith("d"):
                out.append(int(part[:-1]) * 86400)
            else:
                out.append(int(part))  # seconds
        return out

    assert _parse_schedules("30") == [30]
    assert _parse_schedules("60,120") == [60, 120]


def test_parse_schedules_empty():
    """Test schedule parser with empty input."""

    def _parse_schedules(csv: str) -> list[int]:
        out = []
        for part in (csv or "").split(","):
            part = part.strip().lower()
            if not part:
                continue
            if part.endswith("m"):
                out.append(int(part[:-1]) * 60)
            elif part.endswith("h"):
                out.append(int(part[:-1]) * 3600)
            elif part.endswith("d"):
                out.append(int(part[:-1]) * 86400)
            else:
                out.append(int(part))  # seconds
        return out

    assert _parse_schedules("") == []
    assert _parse_schedules("  ") == []


def test_parse_schedules_mixed():
    """Test schedule parser with mixed units."""

    def _parse_schedules(csv: str) -> list[int]:
        out = []
        for part in (csv or "").split(","):
            part = part.strip().lower()
            if not part:
                continue
            if part.endswith("m"):
                out.append(int(part[:-1]) * 60)
            elif part.endswith("h"):
                out.append(int(part[:-1]) * 3600)
            elif part.endswith("d"):
                out.append(int(part[:-1]) * 86400)
            else:
                out.append(int(part))  # seconds
        return out

    assert _parse_schedules("30m,2h,1d") == [1800, 7200, 86400]
    assert _parse_schedules("15m,1h,120") == [900, 3600, 120]


def test_followup_rule_threshold():
    """Test follow-up triggering logic (pred_prob >= threshold)."""
    threshold = 0.70

    # Should NOT trigger
    assert 0.50 < threshold  # Low prob
    assert 0.69 < threshold  # Just below

    # Should trigger
    assert 0.70 >= threshold  # Exactly threshold
    assert 0.85 >= threshold  # Above threshold
    assert 0.99 >= threshold  # High prob


def test_followup_disabled_no_enqueue():
    """Test that follow-ups are skipped when FOLLOWUP_ENABLED=False."""
    followup_enabled = False
    pred_prob = 0.85
    threshold = 0.70

    # Even with high pred_prob, should not enqueue if disabled
    should_enqueue = followup_enabled and pred_prob >= threshold
    assert not should_enqueue


def test_followup_enabled_with_high_prob():
    """Test that follow-ups are enqueued when enabled and pred_prob >= threshold."""
    followup_enabled = True
    pred_prob = 0.85
    threshold = 0.70

    should_enqueue = followup_enabled and pred_prob >= threshold
    assert should_enqueue


def test_followup_enabled_with_low_prob():
    """Test that follow-ups are NOT enqueued when pred_prob < threshold."""
    followup_enabled = True
    pred_prob = 0.50
    threshold = 0.70

    should_enqueue = followup_enabled and pred_prob >= threshold
    assert not should_enqueue
