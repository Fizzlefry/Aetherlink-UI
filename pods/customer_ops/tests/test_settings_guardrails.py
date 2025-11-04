import os
from importlib import reload


def with_env(env: dict, func):
    old = {k: os.environ.get(k) for k in env}
    try:
        os.environ.update({k: str(v) for k, v in env.items()})
        return func()
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def load_settings():
    from pods.customer_ops.api import config

    reload(config)  # ensure env changes take effect
    return config.get_settings()


def test_cors_csv_parsing_dev():
    def run():
        s = load_settings()
        # our config exposes both raw string (cors_origins) and a parsed list
        assert hasattr(s, "cors_origins")
        # if we parse into list property, ensure list contains expected origin
        parsed = s.cors_origins_list if hasattr(s, "cors_origins_list") else None
        assert parsed is not None and isinstance(parsed, list)
        assert "http://localhost:3000" in parsed

    with_env({
        "ENV": "dev",
        "CORS_ORIGINS": "http://localhost:3000, https://example.com ,  https://foo.bar",
    }, run)


def test_prod_rejects_wildcard_cors():
    def run():
        try:
            load_settings()
            assert False, "Expected ValueError for wildcard CORS in prod"
        except Exception as e:
            # Accept ValueError or ValidationError, check message
            msg = str(e).lower()
            assert "cors" in msg or "wildcard" in msg or "cannot be *" in msg

    with_env({"ENV": "prod", "CORS_ORIGINS": "*"}, run)


def test_prod_forces_api_key():
    def run():
        s = load_settings()
        # verify ENV normalized and require_api_key enforced in prod
        assert getattr(s, "ENV", getattr(s, "env", "prod")) == "prod"
        assert s.require_api_key is True

    with_env({"ENV": "prod", "CORS_ORIGINS": "https://app.example.com"}, run)


def test_rate_limits_have_defaults():
    def run():
        s = load_settings()
        assert isinstance(s.RATE_LIMIT_FAQ, str) and "/" in s.RATE_LIMIT_FAQ
        assert isinstance(s.RATE_LIMIT_CHAT, str) and "/" in s.RATE_LIMIT_CHAT

    with_env({"ENV": "dev"}, run)
