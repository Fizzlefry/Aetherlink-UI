from pods.customer_ops.api.config import reload_settings, get_settings

def test_env_keys_to_dict(monkeypatch):
    monkeypatch.setenv("API_KEY_FOO", "K1")
    monkeypatch.setenv("API_KEY_BAR", "K2")
    reload_settings()
    s = get_settings()
    assert s.API_KEYS["K1"] == "FOO"
    assert s.API_KEYS["K2"] == "BAR"
