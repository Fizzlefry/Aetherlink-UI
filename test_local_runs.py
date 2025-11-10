#!/usr/bin/env python3
import json

import requests

# Test the local runs endpoint
try:
    response = requests.get(
        "http://127.0.0.1:8000/api/local/runs", headers={"x-tenant": "the-expert-co"}
    )
    if response.status_code == 200:
        data = response.json()
        print("Local runs endpoint works!")
        print(f"Found {len(data.get('runs', []))} recent runs")
        if data.get("runs"):
            print("Sample run:", json.dumps(data["runs"][0], indent=2))
        else:
            print("No runs yet - let's create one!")
    else:
        print(f"Error: {response.status_code}")
        print(response.text)
except Exception as e:
    print(f"Connection error: {e}")
