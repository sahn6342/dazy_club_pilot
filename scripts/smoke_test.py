"""
smoke_test.py
--------------
Post-deploy smoke test (Detailed-Roadmap.md Phase 1). Hits a live API over
HTTPS and checks: health, a public booking read (slots), and an
authenticated cafe read. Stdlib only - no dependencies to install.

Usage:
    python scripts/smoke_test.py --base-url https://api.example.com \
        --admin-username <ADMIN_USERNAME> --admin-password <ADMIN_PASSWORD>

Credentials can also come from env vars ADMIN_USERNAME / ADMIN_PASSWORD
(the same ones the API container uses) so this can run unattended right
after `docker compose up`:

    python scripts/smoke_test.py --base-url https://api.example.com

Exits 0 on success, 1 with a printed reason on the first failing check.
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import date


def _request(method: str, url: str, body: dict | None = None, token: str | None = None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True, help="e.g. https://api.example.com (no trailing slash, no /api/v1)")
    parser.add_argument("--admin-username", default=os.environ.get("ADMIN_USERNAME"))
    parser.add_argument("--admin-password", default=os.environ.get("ADMIN_PASSWORD"))
    args = parser.parse_args()

    base = args.base_url.rstrip("/") + "/api/v1"
    checks_run = 0

    print(f"[1] GET  {base}/health")
    status, body = _request("GET", f"{base}/health")
    if status != 200 or body.get("status") != "ok":
        print(f"    FAIL - status={status} body={body}")
        return 1
    print("    OK")
    checks_run += 1

    today = date.today().isoformat()
    print(f"[2] GET  {base}/slots?sport=cricket&date={today}  (public booking read)")
    status, body = _request("GET", f"{base}/slots?sport=cricket&date={today}")
    if status != 200 or not isinstance(body, list):
        print(f"    FAIL - status={status} body={body}")
        return 1
    print(f"    OK - {len(body)} slot(s)")
    checks_run += 1

    if not args.admin_username or not args.admin_password:
        print("[3] SKIPPED - no admin credentials supplied (cafe read needs auth)")
        print(f"\n{checks_run}/3 checks passed (1 skipped).")
        return 0

    print(f"[3] POST {base}/admin/login  ->  GET /admin/cafe/categories  (authenticated cafe read)")
    status, body = _request("POST", f"{base}/admin/login", {
        "username": args.admin_username, "password": args.admin_password,
    })
    if status != 200 or "access_token" not in body:
        print(f"    FAIL (login) - status={status} body={body}")
        return 1
    token = body["access_token"]
    status, body = _request("GET", f"{base}/admin/cafe/categories", token=token)
    if status != 200 or not isinstance(body, list):
        print(f"    FAIL (cafe read) - status={status} body={body}")
        return 1
    print(f"    OK - {len(body)} categor(y/ies)")
    checks_run += 1

    print(f"\nAll {checks_run}/3 checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
