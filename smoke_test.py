import os
os.environ["API_KEY_EXPERTCO"]="ABC123"
os.environ["API_KEY_ARGUS"]="XYZ789"
from pods.customer_ops.api.config import get_settings, reload_settings
reload_settings() # reload to pick up env vars
s = get_settings()
print("REQUIRE_API_KEY:", s.REQUIRE_API_KEY)
print("API_KEYS:", s.API_KEYS)
