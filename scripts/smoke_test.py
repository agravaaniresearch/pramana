#!/usr/bin/env python3
"""Post-deployment smoke test. Usage: python scripts/smoke_test.py http://host:8080

Checks that the service is up, the chain verifies, and the headline behaviour holds:
the law judged at 4:00 pm is not changed by a circular published at 5:00 pm.
Exits non-zero on any failure. Uses only the standard library and ignores proxy settings
so it works from inside a locked-down network.
"""
import json
import sys
import urllib.parse
import urllib.request

base = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8080").rstrip("/")
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def get(path, **q):
    url = base + path + ("?" + urllib.parse.urlencode(q) if q else "")
    with opener.open(url, timeout=10) as r:
        return json.load(r)


checks = []


def check(name, ok):
    checks.append(ok)
    print(("PASS  " if ok else "FAIL  ") + name)


h = get("/healthz")
check("service healthy", h.get("status") == "ok" and h.get("entries", 0) > 0)
v = get("/verify")
check("hash chain verifies", v["ok"] is True)
anchor = get("/head")
check("anchor matches chain", get("/verify", anchor=json.dumps(anchor))["ok"] is True)
ins = get("/instruments")["instruments"]
check("instruments listed", len(ins) > 0)

# Only meaningful on the bundled synthetic data; skipped for any other corpus.
if any(i["instrument_id"] == "SYN-FIL-02" for i in ins):
    a = get("/asof", instrument="SYN-FIL-02", at="2024-12-12T16:00:00+05:30")["clauses"]["1.1"]["text"]
    b = get("/asof", instrument="SYN-FIL-02", at="2024-12-12T17:01:00+05:30")["clauses"]["1.1"]["text"]
    check("4:00 pm law is the 60 day rule", "60 days" in a)
    check("5:01 pm law is the 45 day rule", "45 days" in b)
    ex = get("/exposure", instrument="SYN-FIL-02", act="2024-12-12T16:00:00+05:30", hindsight="2025-06-01T00:00:00+05:30")
    check("law judged at 4:00 pm is stable under the rule", ex["tora_delta"] == [])
else:
    print("SKIP  synthetic-data behaviour checks (different corpus)")

sys.exit(0 if all(checks) else 1)
