# pods/customer_ops/tests/test_enrich.py
from pods.customer_ops.api.enrich import enrich_text


def test_enrich_intent_and_urgency():
    e = enrich_text("URGENT: need an estimate for metal roof today")
    assert e["intent"] == "lead_capture"
    assert e["urgency"] == "high"
    assert 0.5 <= e["score"] <= 1.0


def test_enrich_sentiment_positive():
    e = enrich_text("Thanks so much, your service is awesome!")
    assert e["sentiment"] == "positive"


def test_enrich_sentiment_negative():
    e = enrich_text("Very frustrated with the late repair and ongoing problems")
    assert e["sentiment"] == "negative"


def test_enrich_support_intent():
    e = enrich_text("I have a warranty question about a leak repair")
    assert e["intent"] == "support"
