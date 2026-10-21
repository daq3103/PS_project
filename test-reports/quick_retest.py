# -*- coding: utf-8 -*-
import json, uuid, time, socket, http.client, urllib.request, urllib.error
from pathlib import Path
from datetime import datetime
from collections import Counter

HOST, PORT = "localhost", 8000
FE = "http://localhost:3000"
OWNER_EMAIL = "owner@demo.com"
OWNER_PASS = "OwnerPass123"
ts = int(time.time())
R = []

def add(i, f, s, e, a):
    R.append(dict(ID=i, Fn=f, Status=s, Expected=e, Actual=(a or "")[:220]))

def clip(s, n=200):
    return (s or "")[:n]

def port_open(p):
    s = socket.socket(); s.settimeout(2)
    try:
        s.connect(("127.0.0.1", p)); s.close(); return True
    except Exception:
        return False

def redis_pong(port):
    try:
        s = socket.create_connection(("127.0.0.1", port), 2)
        s.sendall(b"PING\r\n"); d = s.recv(64); s.close()
        return b"+PONG" in d
    except Exception:
        return False

def api(method, path, cookies=None, body=None):
    headers = {"Accept": "application/json"}
    payload = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        payload = json.dumps(body)
    if cookies:
        headers["Cookie"] = "; ".join(f"{k}={v}" for k, v in cookies.items())
        if method not in ("GET", "HEAD", "OPTIONS") and "csrf_token" in cookies:
            headers["X-CSRF-Token"] = cookies["csrf_token"]
    conn = http.client.HTTPConnection(HOST, PORT, timeout=30)
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

def http_get(url):
    try:
        with urllib.request.urlopen(url, timeout=20) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:
        return 0, str(e)

def login(email, password):
    return api("POST", "/api/v1/auth/login", body={"email": email, "password": password})

c, b, _ = api("GET", "/healthz")
add("ENV-HEALTH", "Healthz", "PASS" if c == 200 else "FAIL", "200", f"{c} {clip(b)}")

u1e = f"qa.quick.u1.{ts}@example.com"
u1p = "QaTest123!"
u1ph = f"0914{str(ts)[-6:]}"
c, b, _ = api("POST", "/api/v1/auth/register", body={"full_name": "QA Quick One", "password": u1p, "email": u1e, "phone": u1ph})
add("AUTH-REG", "Register customer", "PASS" if c in (200, 201) else "FAIL", "201", f"{c} {clip(b)}")
c1, b1, ck1 = login(u1e, u1p)
add("LOGIN-CUST", "Login customer", "PASS" if c1 == 200 else "FAIL", "200", f"{c1} cookies={list(ck1.keys())} {clip(b1, 80)}")
co, bo, cko = login(OWNER_EMAIL, OWNER_PASS)
role_ok = False
try:
    role_ok = json.loads(bo).get("role") == "owner"
except Exception:
    pass
add("LOGIN-OWNER", "Login owner", "PASS" if co == 200 and role_ok else "FAIL", "200 role=owner", f"{co} role_ok={role_ok} {clip(bo, 80)}")

pg, rc, rq = port_open(5432), port_open(6379), port_open(6380)
add("BUG-03-PG", "Postgres 5432 published", "FAIL" if pg else "PASS", "not published", f"open={pg}")
add("BUG-03-RC", "Redis 6379 published", "FAIL" if rc else "PASS", "not published", f"open={rc}")
add("BUG-03-RQ", "Redis 6380 published", "FAIL" if rq else "PASS", "not published", f"open={rq}")
p1 = redis_pong(6379) if rc else False
p2 = redis_pong(6380) if rq else False
add("BUG-03-AUTH", "Redis no-auth PING fails", "PASS" if (not p1 and not p2) else "FAIL", "no PONG without AUTH", f"6379_pong={p1} 6380_pong={p2}")

c, b = http_get(FE + "/admin")
add("BUG-08", "Admin UI anon", "PASS" if c in (301, 302, 401, 403) or (c == 200 and len(b) < 500) else "FAIL", "redirect/block", f"{c} len={len(b)}")
c, b, _ = api("GET", "/api/v1/admin/dashboard")
add("ADMIN-API-ANON", "Admin API anon", "PASS" if c in (401, 403) else "FAIL", "401/403", f"{c} {clip(b)}")

c, b, _ = api("GET", "/api/v1/products?limit=5")
variant_id = stock_qty = None
if c == 200:
    items = json.loads(b)
    if isinstance(items, dict):
        items = items.get("items") or items.get("products") or []
    for p in items or []:
        cd, bd, _ = api("GET", f"/api/v1/products/{p['id']}")
        if cd != 200:
            continue
        vs = json.loads(bd).get("variants") or []
        if vs:
            variant_id = vs[0]["id"]
            stock_qty = vs[0].get("cached_available_qty")
            cs, bs, _ = api("GET", f"/api/v1/products/{p['id']}/stock")
            if cs == 200:
                for v in (json.loads(bs).get("variants") or []):
                    if v.get("variant_id") == variant_id:
                        stock_qty = v.get("cached_available_qty", stock_qty)
                        break
            break
add("PROD", "Resolve variant", "PASS" if variant_id else "BLOCKED", "variant", f"v={variant_id} stock={stock_qty}")

if variant_id and c1 == 200:
    over = (int(stock_qty) + 40) if isinstance(stock_qty, int) else 99
    c, b, ck1 = api("POST", "/api/v1/cart/items", ck1, {"variant_id": variant_id, "qty": over})
    add("BUG-04", "Cart qty > stock", "PASS" if c in (400, 409, 422) else "FAIL", "reject", f"{c} over={over} stock={stock_qty} {clip(b)}")
    c, b, ck1 = api("GET", "/api/v1/cart", ck1)
    if c == 200:
        for it in (json.loads(b).get("items") or []):
            _, _, ck1 = api("DELETE", f"/api/v1/cart/items/{it['id']}", ck1)
else:
    add("BUG-04", "Cart qty > stock", "BLOCKED", "reject", "no login/variant")

ship = {"province_id": 202, "province_name": "HCM", "district_id": 1442, "district_name": "Q1", "ward_code": "1A0101", "ward_name": "Ben Nghe", "street_address": "77 QA Quick"}
guest_phone = "0977001122"
order_code = None
if variant_id:
    body = {
        "idempotency_key": str(uuid.uuid4()),
        "customer_name": "QA Quick Guest",
        "customer_phone": guest_phone,
        "customer_email": f"qa.quick.guest.{ts}@example.com",
        "shipping_address": ship,
        "payment_method": "cod",
        "items": [{"variant_id": variant_id, "qty": 1}],
    }
    c, b, _ = api("POST", "/api/v1/checkout", body=body)
    add("COD-GUEST", "Guest COD checkout", "PASS" if c in (200, 201) else "FAIL", "201", f"{c} {clip(b)}")
    if c in (200, 201):
        order_code = json.loads(b).get("order_code")
else:
    add("COD-GUEST", "Guest COD checkout", "BLOCKED", "201", "no variant")

if order_code:
    c, b, _ = api("GET", f"/api/v1/orders/track?order_code={order_code}&phone={guest_phone}")
    if c != 200:
        c, b, _ = api("GET", f"/api/v1/orders/track?order_code={order_code}&customer_phone={guest_phone}")
    add("TRACK", "Track guest order", "PASS" if c == 200 else "FAIL", "200", f"{c} {clip(b)}")
else:
    add("TRACK", "Track guest order", "BLOCKED", "200", "no order")

if variant_id and c1 == 200:
    body = {
        "idempotency_key": str(uuid.uuid4()),
        "customer_name": "QA Quick One",
        "customer_phone": u1ph,
        "shipping_address": {**ship, "street_address": "12 QA Quick VietQR"},
        "payment_method": "vietqr",
        "items": [{"variant_id": variant_id, "qty": 1}],
    }
    c, b, ck1 = api("POST", "/api/v1/checkout", ck1, body)
    if c in (200, 201):
        oj = json.loads(b)
        pid, st, pay = oj["id"], oj.get("status"), oj.get("payment_status")
        c2, b2, ck1 = api("POST", f"/api/v1/orders/{pid}/confirm", ck1, {})
        if c2 == 200:
            after = json.loads(b2)
            bad = after.get("status") == "confirmed" and after.get("payment_status") == "unpaid"
            add("BUG-02", "Customer self-confirm unpaid VietQR", "FAIL" if bad else "PASS", "reject / keep unpaid",
                f"confirm={c2} before={st}/{pay} after={after.get('status')}/{after.get('payment_status')}")
        else:
            add("BUG-02", "Customer self-confirm unpaid VietQR", "PASS" if c2 in (401, 403, 400, 409) else "FAIL", "403/409",
                f"{c2} before={st}/{pay} {clip(b2)}")
    else:
        add("BUG-02", "Customer self-confirm unpaid VietQR", "BLOCKED", "reject confirm", f"checkout {c} {clip(b)}")
else:
    add("BUG-02", "Customer self-confirm unpaid VietQR", "BLOCKED", "reject", "no login/variant")

if co == 200:
    c, b, cko = api("GET", "/api/v1/admin/dashboard", cko)
    add("OWN-DASH", "Owner dashboard", "PASS" if c == 200 else "FAIL", "200", f"{c} {clip(b, 100)}")
    c, b, cko = api("GET", "/api/v1/admin/orders", cko)
    add("OWN-ORDERS", "Owner list orders", "PASS" if c == 200 else "FAIL", "200", f"{c} len={len(b)}")
    c, b, ck1 = api("GET", "/api/v1/admin/dashboard", ck1)
    add("OWN-AUTHZ", "Customer blocked admin", "PASS" if c in (401, 403) else "FAIL", "403", f"{c} {clip(b)}")
else:
    for i, f in [("OWN-DASH", "dashboard"), ("OWN-ORDERS", "orders"), ("OWN-AUTHZ", "authz")]:
        add(i, f, "BLOCKED", "-", "owner login failed")

out = Path(r"D:\code\PS_project\test-reports")
out.mkdir(parents=True, exist_ok=True)
(out / "quick-retest-results.json").write_text(json.dumps({"ts": ts, "results": R}, ensure_ascii=False, indent=2), encoding="utf-8")
print("COUNTS", dict(Counter(x["Status"] for x in R)), "TOTAL", len(R))
for x in R:
    print("%-8s %-16s %s" % (x["Status"], x["ID"], x["Actual"][:140]))
