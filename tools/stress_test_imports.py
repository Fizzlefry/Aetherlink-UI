import argparse
import json
import random
import time
import urllib.request


def post(url, headers=None, data=None):
    req = urllib.request.Request(url, method="POST")
    if headers:
        for k, v in headers.items():
            req.add_header(k, v)
    if data is not None:
        body = json.dumps(data).encode("utf-8")
        req.add_header("Content-Type", "application/json")
        req.data = body
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-base", default="http://127.0.0.1:8000")
    parser.add_argument("--tenant", default="stress-tenant")
    parser.add_argument("--count", type=int, default=50)
    parser.add_argument("--min-delay", type=float, default=0.2)
    parser.add_argument("--max-delay", type=float, default=1.2)
    args = parser.parse_args()

    # ensure schedule
    try:
        post(
            f"{args.api_base}/api/crm/import/acculynx/schedule",
            headers={"x-tenant": args.tenant, "x-ops": "1"},
            data={"interval_sec": 180},
        )
        print(f"[init] ensured schedule for {args.tenant}")
    except Exception as e:
        print(f"[init] schedule create failed (maybe exists): {e}")

    ok = 0
    fail = 0
    for i in range(1, args.count + 1):
        try:
            result = post(
                f"{args.api_base}/api/crm/import/acculynx/run-now",
                headers={"x-tenant": args.tenant, "x-ops": "1"},
            )
            if result.get("ok"):
                ok += 1
                print(f"[{i}/{args.count}] OK: {result.get('message')}")
            else:
                fail += 1
                print(f"[{i}/{args.count}] FAIL: backend not ok")
        except Exception as e:
            fail += 1
            print(f"[{i}/{args.count}] ERROR: {e}")

        time.sleep(random.uniform(args.min_delay, args.max_delay))

    print("=== STRESS DONE ===")
    print(f"OK   : {ok}")
    print(f"FAIL : {fail}")


if __name__ == "__main__":
    main()
