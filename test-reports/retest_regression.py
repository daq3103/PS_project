# -*- coding: utf-8 -*-
"""Regression for BUG-01..10 + smoke. Non-destructive."""
import json, uuid, time, socket, http.client, urllib.request, urllib.error
from pathlib import Path
from collections import Counter
from datetime import datetime

BASE_HOST, BASE_PORT = "localhost", 8000
FE = "http://localhost:3000"
NGINX = "http://localhost"
REPORT_DIR = Path(r"D:\code\PS_project\test-reports")
OWNER_EMAIL = "owner@demo.com"
OWNER_PASS = "OwnerPass123"  # never print in report
ts = int(time.time())
results = []

def add(tid, fn, status, expected, actual, evidence=""):
    results.append({
        "ID": tid, "Fn": fn, "Status": status,
        "Expected": expected, "Actual": actual, "Evidence": evidence,
    })

def clip(s, n=200):
    return (s or "")[:n]

def port_open(port):
    s = socket.socket()
    s.settimeout(2)
    try:
        s.connect(("127.0.0.1", port))
        s.close()
        return True
    except Exception:
        return False

def http_raw(method, url, body=None, headers=None, timeout=30):
    data = None
    h = {"Accept": "application/json"}
    if headers:
        h.update(headers)
    if body is not None:
        data = json.dumps(body).encode()
        h["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace"), dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace"), dict(e.headers)
    except Exception as e:
        return 0, str(e), {}

def api(method, path, cookies=None, body=None, extra=None):
    headers = {"Accept": "application/json"}
    payload = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        payload = json.dumps(body)
    if cookies:
        headers["Cookie"] = "; ".join(f"{k}={v}" for k, v in cookies.items())
        if method not in ("GET", "HEAD", "OPTIONS") and "csrf_token" in cookies:
            headers["X-CSRF-Token"] = cookies["csrf_token"]
    if extra:
        headers.update(extra)
    conn = http.client.HTTPConnection(BASE_HOST, BASE_PORT, timeout=30)
    conn.request(method, path, body=payload, headers=headers)
    resp = conn.getresponse()
    data = resp.read().decode("utf-8", "replace")
    code = resp.status
    newc = dict(cookies or {})
    for k, v in resp.getheaders():
        if k.lower() == "set-cookie":
            part = v.split(";", 1)[0]
            if "=" in part:
                n, val = part.split("=", 1)
                newc[n] = val
    conn.close()
    return code, data, newc

def login(email, password):
    return api("POST", "/api/v1/auth/login", body={"email": email, "password": password})

def redis_noauth(port):
    try:
        s = socket.create_connection(("127.0.0.1", port), timeout=2)
        s.sendall(b"PING\r\n")
        data = s.recv(64)
        s.close()
        return b"+PONG" in data
    except Exception as e:
        return False

# ---------- ENV / SMOKE ----------
c, b, _ = api("GET", "/healthz")
add("SMOKE-HEALTH", "Healthz", "PASS" if c == 200 else "FAIL", "200", f"{c} {clip(b)}")
c, b, _ = api("GET", "/readyz")
add("SMOKE-READY", "Readyz", "PASS" if c == 200 else "FAIL", "200", f"{c} {clip(b)}")

c, b, hdrs = http_raw("GET", FE + "/")
add("SMOKE-HOME", "Home FE :3000", "PASS" if c == 200 and len(b) > 500 else "FAIL", "200 HTML", f"{c} len={len(b)}")

c, b, _ = http_raw("GET", NGINX + "/")
add("SMOKE-NGINX", "Home via nginx :80", "PASS" if c == 200 else "FAIL", "200", f"{c} len={len(b) if b else 0}")

# ---------- BUG-01 GHN unsigned ----------
c, b, _ = api("POST", "/api/v1/webhooks/ghn", body={
    "OrderCode": f"QA-RETEST-{ts}",
    "Status": "delivered",
    "Type": "switch_status",
    "Time": ts,
})
# PASS if rejected 401/403; FAIL if accepted 200
add("BUG-01", "GHN webhook unsigned",
    "PASS" if c in (401, 403) else "FAIL",
    "401/403 reject unsigned",
    f"{c} {clip(b)}")

# ---------- BUG-06 invalid phone (do early) ----------
c, b, _ = api("POST", "/api/v1/auth/register", body={
    "full_name": "QA Retest BadPhone",
    "password": "QaTest123!",
    "email": f"qa.retest.phone.{ts}@example.com",
    "phone": "12ab34cd56",
})
add("BUG-06", "Register invalid phone",
    "PASS" if c in (400, 422) else "FAIL",
    "400/422",
    f"{c} {clip(b)}")

# ---------- BUG-09 XSS name store ----------
xss_email = f"qa.retest.xss.{ts}@example.com"
c, b, _ = api("POST", "/api/v1/auth/register", body={
    "full_name": "<img src=x onerror=alert(1)>QA",
    "password": "QaTest123!",
    "email": xss_email,
    "phone": f"0905{str(ts)[-6:]}",
})
xss_reg = c
stored_raw = "<img" in (b or "")
# BUG-09: sanitize on write → PASS if rejected OR stored without raw tags
if c in (400, 422):
    add("BUG-09", "Sanitize full_name on write", "PASS", "reject or strip HTML", f"{c} rejected")
elif c in (200, 201) and not stored_raw:
    add("BUG-09", "Sanitize full_name on write", "PASS", "strip HTML", f"{c} no raw tag in response")
else:
    add("BUG-09", "Sanitize full_name on write", "FAIL", "sanitize/strip", f"{c} hasRaw={stored_raw} {clip(b)}")

# ---------- Auth users ----------
u1e, u1p, u1ph = f"qa.retest.u1.{ts}@example.com", "QaTest123!", f"0913{str(ts)[-6:]}"
c, b, _ = api("POST", "/api/v1/auth/register", body={
    "full_name": "QA Retest One", "password": u1p, "email": u1e, "phone": u1ph,
})
add("SMOKE-REG", "Register customer", "PASS" if c in (200, 201) else "FAIL", "201", f"{c} {clip(b)}")

c1, b1, ck1 = login(u1e, u1p)
add("SMOKE-LOGIN", "Login customer", "PASS" if c1 == 200 else "FAIL", "200", f"{c1} cookies={list(ck1.keys())}")

co, bo, cko = login(OWNER_EMAIL, OWNER_PASS)
role_ok = False
try:
    role_ok = json.loads(bo).get("role") == "owner"
except Exception:
    pass
add("SMOKE-OWNER-LOGIN", "Login owner demo", "PASS" if co == 200 and role_ok else "FAIL", "200 role=owner", f"{co} role_ok={role_ok}")

# ---------- BUG-08 admin UI shell ----------
c, b, _ = http_raw("GET", FE + "/admin")
# PASS if redirect/block (not serving large admin shell to anon)
if c in (301, 302, 401, 403):
    add("BUG-08", "Admin UI without login", "PASS", "redirect/block", f"{c} len={len(b)}")
elif c == 200 and len(b) > 500:
    # check if page forces login client-side — still FAIL per prior criteria (shell visible)
    add("BUG-08", "Admin UI without login", "FAIL", "redirect/block UI", f"{c} len={len(b)}")
else:
    add("BUG-08", "Admin UI without login", "FAIL", "redirect/block", f"{c} len={len(b)}")

c, b, _ = api("GET", "/api/v1/admin/dashboard")
add("SMOKE-ADMIN-API-ANON", "Admin API anon", "PASS" if c in (401, 403) else "FAIL", "401/403", f"{c} {clip(b)}")

# ---------- BUG-07 security headers ----------
c, b, hdrs = http_raw("GET", FE + "/")
hl = {k.lower(): v for k, v in hdrs.items()}
need = [
    "content-security-policy", "x-frame-options", "x-content-type-options",
    "strict-transport-security", "referrer-policy",
]
# also check nginx
c2, b2, hdrs2 = http_raw("GET", NGINX + "/")
hl2 = {k.lower(): v for k, v in hdrs2.items()}
missing_fe = [n for n in need if n not in hl]
missing_nx = [n for n in need if n not in hl2]
# PASS if either FE or nginx provides them (ideally both)
if not missing_nx or not missing_fe:
    # if one surface has all, partial credit — require at least nginx OR fe fully
    ok = (not missing_nx) or (not missing_fe)
else:
    ok = False
# stricter: PASS only if FE :3000 has them OR nginx has them (all 5)
ok = (len(missing_fe) == 0) or (len(missing_nx) == 0)
add("BUG-07", "Security headers FE/nginx",
    "PASS" if ok else "FAIL",
    "CSP/XFO/XCTO/HSTS/RP on FE or nginx",
    f"fe_missing={missing_fe}; nginx_missing={missing_nx}")

# ---------- BUG-03 / ports + redis auth ----------
pg = port_open(5432)
rc = port_open(6379)
rq = port_open(6380)
# PASS if NOT published OR (published but only localhost - still FAIL if open on host per prior criteria)
# Prior expected: not published. Keep same bar.
add("BUG-03a", "Postgres 5432 not published", "PASS" if not pg else "FAIL", "not open on host", f"open={pg}")
add("BUG-03b", "Redis 6379 not published", "PASS" if not rc else "FAIL", "not open on host", f"open={rc}")
add("BUG-03c", "Redis 6380 not published", "PASS" if not rq else "FAIL", "not open on host", f"open={rq}")
pong6379 = redis_noauth(6379) if rc else False
pong6380 = redis_noauth(6380) if rq else False
# PASS if requirepass (PING without auth fails) OR port closed
add("BUG-03d", "Redis requires auth",
    "PASS" if (not pong6379 and not pong6380) else "FAIL",
    "PING without AUTH fails",
    f"6379_pong={pong6379} 6380_pong={pong6380}")

# ---------- Products / variant / stock ----------
c, b, _ = api("GET", "/api/v1/products?limit=5")
add("SMOKE-PRODUCTS", "List products", "PASS" if c == 200 else "FAIL", "200", f"{c} {clip(b, 80)}")
variant_id = None
stock_qty = None
prod_id = None
if c == 200:
    items = json.loads(b)
    if isinstance(items, dict):
        items = items.get("items") or items.get("data") or items.get("products") or []
    for p in items or []:
        prod_id = p.get("id")
        cd, bd, _ = api("GET", f"/api/v1/products/{prod_id}")
        if cd != 200:
            continue
        d = json.loads(bd)
        variants = d.get("variants") or []
        if variants:
            variant_id = variants[0]["id"]
            stock_qty = variants[0].get("cached_available_qty")
            cs, bs, _ = api("GET", f"/api/v1/products/{prod_id}/stock")
            if cs == 200:
                sj = json.loads(bs)
                for v in (sj.get("variants") or []):
                    if v.get("variant_id") == variant_id:
                        stock_qty = v.get("cached_available_qty", stock_qty)
                        break
            break
add("SMOKE-VARIANT", "Resolve variant+stock", "PASS" if variant_id else "BLOCKED", "have variant", f"v={variant_id} stock={stock_qty}")

# ---------- BUG-04 cart overstock ----------
if variant_id and c1 == 200:
    over = (int(stock_qty) + 49) if isinstance(stock_qty, int) else 99
    c, b, ck1 = api("POST", "/api/v1/cart/items", ck1, {"variant_id": variant_id, "qty": over})
    add("BUG-04", "Cart qty > stock",
        "PASS" if c in (400, 409, 422) else "FAIL",
        "reject overstock",
        f"{c} over={over} stock={stock_qty} {clip(b)}")
    # cleanup + add 1 for checkout smoke
    c, b, ck1 = api("GET", "/api/v1/cart", ck1)
    if c == 200:
        for it in (json.loads(b).get("items") or []):
            _, _, ck1 = api("DELETE", f"/api/v1/cart/items/{it['id']}", ck1)
    c, b, ck1 = api("POST", "/api/v1/cart/items", ck1, {"variant_id": variant_id, "qty": 1})
    add("SMOKE-CART", "Add cart qty=1", "PASS" if c in (200, 201) else "FAIL", "200", f"{c} {clip(b, 100)}")
else:
    add("BUG-04", "Cart qty > stock", "BLOCKED", "reject", "no variant/login")
    add("SMOKE-CART", "Add cart qty=1", "BLOCKED", "200", "no variant/login")

# ---------- SMOKE COD checkout guest + track ----------
ship = {
    "province_id": 202, "province_name": "HCM", "district_id": 1442, "district_name": "Q1",
    "ward_code": "1A0101", "ward_name": "Ben Nghe", "street_address": "88 QA Retest St",
}
guest_phone = "0977123456"
order_id = order_code = None
if variant_id:
    body = {
        "idempotency_key": str(uuid.uuid4()),
        "customer_name": "QA Retest Guest",
        "customer_phone": guest_phone,
        "customer_email": f"qa.retest.guest.{ts}@example.com",
        "shipping_address": ship,
        "payment_method": "cod",
        "items": [{"variant_id": variant_id, "qty": 1}],
    }
    c, b, _ = api("POST", "/api/v1/checkout", body=body)
    add("SMOKE-COD", "Guest COD checkout", "PASS" if c in (200, 201) else "FAIL", "201", f"{c} {clip(b)}")
    if c in (200, 201):
        oj = json.loads(b)
        order_id, order_code = oj.get("id"), oj.get("order_code")
else:
    add("SMOKE-COD", "Guest COD checkout", "BLOCKED", "201", "no variant")

if order_id:
    c, b, _ = api("GET", f"/api/v1/orders/track?order_code={order_code}&phone={guest_phone}")
    if c != 200:
        c, b, _ = api("GET", f"/api/v1/orders/track?order_code={order_code}&customer_phone={guest_phone}")
    add("SMOKE-TRACK", "Track guest order", "PASS" if c == 200 else "FAIL", "200 masked", f"{c} {clip(b)}")
else:
    add("SMOKE-TRACK", "Track guest order", "BLOCKED", "200", "no order")

# ---------- BUG-02 customer self-confirm unpaid VietQR ----------
if variant_id and c1 == 200:
    body = {
        "idempotency_key": str(uuid.uuid4()),
        "customer_name": "QA Retest One",
        "customer_phone": u1ph,
        "shipping_address": {**ship, "street_address": "12 QA Retest Pending"},
        "payment_method": "vietqr",
        "items": [{"variant_id": variant_id, "qty": 1}],
    }
    c, b, ck1 = api("POST", "/api/v1/checkout", ck1, body)
    if c in (200, 201):
        oj = json.loads(b)
        pid = oj["id"]
        st, pay = oj.get("status"), oj.get("payment_status")
        c2, b2, ck1 = api("POST", f"/api/v1/orders/{pid}/confirm", ck1, {})
        # PASS if blocked (403/409/400) OR still pending unpaid; FAIL if 200 confirmed while unpaid
        if c2 == 200:
            try:
                after = json.loads(b2)
                bad = after.get("status") == "confirmed" and after.get("payment_status") == "unpaid"
            except Exception:
                bad = True
            add("BUG-02", "Customer self-confirm unpaid VietQR",
                "FAIL" if bad else "PASS",
                "reject or keep unpaid pending",
                f"confirm={c2} before={st}/{pay} after={clip(b2)}")
        else:
            add("BUG-02", "Customer self-confirm unpaid VietQR",
                "PASS" if c2 in (401, 403, 409, 400) else "FAIL",
                "403/409 reject customer confirm",
                f"{c2} before={st}/{pay} {clip(b2)}")
    else:
        add("BUG-02", "Customer self-confirm unpaid VietQR", "BLOCKED", "reject confirm", f"checkout {c} {clip(b)}")
else:
    add("BUG-02", "Customer self-confirm unpaid VietQR", "BLOCKED", "reject", "no variant/login")

# ---------- SMOKE owner reads ----------
if co == 200:
    c, b, cko = api("GET", "/api/v1/admin/dashboard", cko)
    add("SMOKE-OWN-DASH", "Owner dashboard", "PASS" if c == 200 else "FAIL", "200", f"{c} {clip(b, 120)}")
    c, b, cko = api("GET", "/api/v1/admin/orders", cko)
    add("SMOKE-OWN-ORDERS", "Owner list orders", "PASS" if c == 200 else "FAIL", "200", f"{c} len={len(b)}")
    c, b, ck1 = api("GET", "/api/v1/admin/dashboard", ck1)
    add("SMOKE-AUTHZ", "Customer blocked from admin", "PASS" if c in (401, 403) else "FAIL", "403", f"{c} {clip(b)}")
else:
    for tid, fn in [("SMOKE-OWN-DASH", "dashboard"), ("SMOKE-OWN-ORDERS", "orders"), ("SMOKE-AUTHZ", "authz")]:
        add(tid, fn, "BLOCKED", "-", "owner login failed")

# ---------- BUG-05 nginx 502 (current stability) ----------
c, b, _ = http_raw("GET", NGINX + "/")
c2, b2, _ = http_raw("GET", NGINX + "/api/v1/categories")
ok502 = c == 200 and c2 == 200
add("BUG-05", "Nginx proxy stable (no 502 now)",
    "PASS" if ok502 else "FAIL",
    "200 FE+API via nginx",
    f"fe={c} api={c2} {clip(b2, 60)}")

# ---------- BUG-10 tooling quick ----------
# ruff/mypy/pytest — run via docker if possible; mark from subprocess later in shell wrapper
# placeholders filled by outer shell writing TOOL results into same file
add("BUG-10a", "ruff check (placeholder)", "NOT RUN", "0 errors", "filled by runner")
add("BUG-10b", "mypy (placeholder)", "NOT RUN", "0 errors", "filled by runner")
add("BUG-10c", "pytest encryption (placeholder)", "NOT RUN", "pass", "filled by runner")

REPORT_DIR.mkdir(parents=True, exist_ok=True)
(REPORT_DIR / "retest-results.json").write_text(
    json.dumps({"ts": ts, "results": results, "meta": {
        "variant_id": variant_id, "stock_qty": stock_qty,
        "guest_order": order_code, "guest_order_id": order_id,
    }}, ensure_ascii=False, indent=2),
    encoding="utf-8",
)
cnt = Counter(r["Status"] for r in results)
print("COUNTS", dict(cnt), "TOTAL", len(results))
for r in results:
    print(f"{r['Status']:8} {r['ID']:22} {clip(r['Actual'], 140)}")
print("META", json.dumps({"variant": variant_id, "stock": stock_qty, "guest": order_code}))
