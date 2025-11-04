import pytest

from pods.customer_ops.api.config import Settings


def test_defaults_load():
    s = Settings()  # uses defaults if no env
    assert s.APP_NAME and s.RATE_LIMIT_FAQ.endswith("/minute")


def test_invalid_log_level_raises(monkeypatch):
    monkeypatch.setenv("LOG_LEVEL", "NOPE")
    with pytest.raises(Exception):
        Settings()


def test_block_wildcard_cors_in_prod(monkeypatch):
    monkeypatch.setenv("ENV", "prod")
    monkeypatch.setenv("CORS_ORIGINS", "*")
    with pytest.raises(Exception):
        Settings()
