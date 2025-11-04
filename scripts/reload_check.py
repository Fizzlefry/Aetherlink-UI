import json
import os
import sys
from pathlib import Path

# Ensure imports find the project root when running this script directly.
# Insert the repository root (two levels up from scripts/) into sys.path.
repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

# configure env - mimic the test that should enable API key enforcement
# Force these values for the purposes of this local check (override any global env).
os.environ["REQUIRE_API_KEY"] = "true"
os.environ["API_KEYS"] = "acme:ACME_KEY"

from fastapi.testclient import TestClient

# Import the app
from pods.customer_ops.api.main import app, get_settings

# Use the module-level app which has the v1 endpoints attached by the file-level decorators
client = TestClient(app)

print("Before reload, require_api_key:", get_settings().require_api_key)
print("Registered routes:")
for route in app.routes:
    try:
        print(" ", route.path)
    except Exception:
        pass

r = client.get("/ops/reload")
print("/ops/reload status:", r.status_code)
try:
    print("/ops/reload body:", json.dumps(r.json(), indent=2))
except Exception:
    print("/ops/reload body not JSON, raw:", r.text)

print("After reload, require_api_key:", get_settings().require_api_key)
print("env REQUIRE_API_KEY:", os.environ.get("REQUIRE_API_KEY"))
print("settings dump:", get_settings().model_dump())

# Now attempt to POST to /v1/lead without Authorization header
lead_payload = {"name": "Test", "phone": "555-0100", "details": "hi"}
post = client.post("/v1/lead", json=lead_payload)
print("POST /v1/lead status:", post.status_code)
try:
    print("POST /v1/lead body:", json.dumps(post.json(), indent=2))
except Exception:
    print("POST /v1/lead raw:", post.text)

# Now try with the x-api-key header (required by the auth dependency)
headers = {"x-api-key": "ACME_KEY"}
post2 = client.post("/v1/lead", json=lead_payload, headers=headers)
print("POST with key status:", post2.status_code)
try:
    print("POST with key body:", json.dumps(post2.json(), indent=2))
except Exception:
    print("POST with key raw:", post2.text)
