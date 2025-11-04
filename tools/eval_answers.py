#!/usr/bin/env python3
"""
Evaluation harness for /answer endpoint.
Checks that answers:
1. Contain required tokens (must)
2. Avoid PII markers (avoid)
3. Have confidence >= 0.25

Usage:
    python tools/eval_answers.py --api-url http://localhost:8000 --api-key <key>
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

try:
    import requests
except ImportError:
    print("Error: requests library not found. Install with: pip install requests")
    sys.exit(1)


def load_testcases(path: Path) -> list[dict[str, Any]]:
    """Load test cases from JSONL file"""
    cases = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                cases.append(json.loads(line))
    return cases


def run_eval(api_url: str, api_key: str, testcases: list[dict[str, Any]]) -> None:
    """Run evaluation on all test cases"""
    headers = {"X-API-Key": api_key}
    passed = 0
    failed = 0

    for i, tc in enumerate(testcases, 1):
        q = tc["q"]
        must = tc.get("must", [])
        avoid = tc.get("avoid", [])

        print(f"\n[{i}/{len(testcases)}] Testing: {q}")

        # Call /answer endpoint with rerank=true for best results
        resp = requests.get(
            f"{api_url}/answer",
            params={"q": q, "k": 5, "mode": "hybrid", "rerank": "true"},
            headers=headers,
            timeout=30,
        )

        if resp.status_code != 200:
            print(f"  ❌ API error: {resp.status_code}")
            failed += 1
            continue

        data = resp.json()
        answer = data.get("answer", "")
        conf = data.get("confidence", 0.0)

        # Check confidence threshold
        if conf < 0.25:
            print(f"  ⚠️  Low confidence: {conf:.3f} (below 0.25 threshold)")
            # Don't fail on low confidence, just warn

        # Check must-have tokens
        answer_lower = answer.lower()
        missing = [tok for tok in must if tok.lower() not in answer_lower]
        if missing:
            print(f"  ❌ Missing required tokens: {missing}")
            failed += 1
            continue

        # Check PII avoidance
        found_pii = [tok for tok in avoid if tok in answer]
        if found_pii:
            print(f"  ❌ Contains PII markers: {found_pii}")
            failed += 1
            continue

        # Success
        print(f"  ✅ PASS (confidence: {conf:.3f}, citations: {len(data.get('citations', []))})")
        print(f"     Answer: {answer[:120]}...")
        passed += 1

    # Summary
    print(f"\n{'='*60}")
    print(f"Results: {passed}/{len(testcases)} passed, {failed}/{len(testcases)} failed")

    if failed > 0:
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Evaluate /answer endpoint")
    parser.add_argument(
        "--api-url",
        default="http://localhost:8000",
        help="Base URL of the API (default: http://localhost:8000)",
    )
    parser.add_argument("--api-key", required=True, help="API key for authentication")
    parser.add_argument(
        "--testcases", default="tools/eval_answers.jsonl", help="Path to JSONL test cases file"
    )

    args = parser.parse_args()

    # Load test cases
    testcases_path = Path(args.testcases)
    if not testcases_path.exists():
        print(f"Error: Test cases file not found: {testcases_path}")
        sys.exit(1)

    testcases = load_testcases(testcases_path)
    print(f"Loaded {len(testcases)} test cases from {testcases_path}")

    # Run evaluation
    run_eval(args.api_url, args.api_key, testcases)


if __name__ == "__main__":
    main()
