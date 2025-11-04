import contextlib
import importlib
import os

import pytest


def reload_settings_module():
    mod = importlib.import_module("api.config")
    importlib.reload(mod)
    return mod


@contextlib.contextmanager
def env_vars(**pairs):
    old = {k: os.environ.get(k) for k in pairs}
    try:
        for k, v in pairs.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = str(v)
        yield
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


@pytest.fixture(autouse=True)
def _fresh_settings_env(monkeypatch):
    # Default safe env for all tests
    with env_vars(
        DATABASE_URL="sqlite:///:memory:",
        REQUIRE_API_KEY="false",
        REDIS_URL=None,
        ENV="dev",
        CORS_ORIGINS="http://localhost:3000",
    ):
        # Clear any module-level singletons/caches
        mod = reload_settings_module()
        if hasattr(mod, "reload_settings"):
            mod.reload_settings()
        yield
