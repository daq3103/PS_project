# -*- coding: utf-8 -*-
import json
from pathlib import Path
from collections import Counter
from datetime import datetime

REPORT_DIR = Path(r"D:\code\PS_project\test-reports")
data = json.loads((REPORT_DIR / "retest-results.json").read_text(encoding="utf-8"))
results = data["results"]
by = {r["ID"]: r for r in results}

def upsert(i, f, s, e, a, ev=""):
    by[i] = {"ID": i, "Fn": f, "Status": s, "Expected": e, "Actual": a, "Evidence": ev}

# Fill BUG-10 from this run
upsert("BUG-10a", "ruff check app", "FAIL", "0 errors", "132 errors (was 130)", "B008/E501/F401/...")
upsert("BUG-10b", "mypy app", "FAIL", "0 errors", "15 errors in 6 files (same ballpark)", "")
upsert("BUG-10c", "pytest encryption", "PASS", "pass", "1 passed", "")
upsert("BUG-10", "Tooling overall (ruff/mypy/suite)", "FAIL", "clean lint + meaningful suite", "ruff 132, mypy 15, only encryption pytest", "")

# Aggregate BUG-03
b03_ports = all(by[k]["Status"] == "PASS" for k in ("BUG-03a", "BUG-03b", "BUG-03c") if k in by)
b03_auth = by.get("BUG-03d", {}).get("Status") == "PASS"
if b03_ports and b03_auth:
    upsert("BUG-03", "DB/Redis exposure + Redis auth", "PASS", "ports closed + requirepass", "all good")
elif b03_auth and not b03_ports:
    upsert("BUG-03", "DB/Redis exposure + Redis auth", "FAIL", "ports closed + requirepass", "requirepass OK but 5432/6379/6380 still published on host")
else:
    upsert("BUG-03", "DB/Redis exposure + Redis auth", "FAIL", "ports closed + requirepass", f"ports_ok={b03_ports} auth_ok={b03_auth}")

# New regression explicit
upsert("REG-NEW-01", "Login broken after Redis requirepass", "FAIL", "200 login", "500 AuthenticationError: Redis auth required; API/worker cannot connect", "P0 new regression")
upsert("REG-NEW-02", "Worker crash loop", "FAIL", "worker healthy", "fastapi-worker Restarting; Redis AuthenticationError", "P0")
upsert("REG-NEW-03", "Checkout COD guest", "FAIL", "201", by.get("SMOKE-COD", {}).get("Actual", "500"), "blocked by Redis auth mismatch")

results = sorted(by.values(), key=lambda x: x["ID"])
(REPORT_DIR / "retest-results.json").write_text(
    json.dumps({"ts": data.get("ts"), "meta": data.get("meta"), "results": results}, ensure_ascii=False, indent=2),
    encoding="utf-8",
)
cnt = Counter(r["Status"] for r in results)

# Compare to previous bug status
prev = {
    "BUG-01": "FAIL",
    "BUG-02": "FAIL",
    "BUG-03": "FAIL",
    "BUG-04": "FAIL",
    "BUG-05": "PASS",  # was risk noted but current stable PASS in prior report appendix
    "BUG-06": "FAIL",
    "BUG-07": "FAIL",
    "BUG-08": "FAIL",
    "BUG-09": "FAIL",
    "BUG-10": "FAIL",
}
# Prior BUG-05 was listed as risk/P2 but INT-502 was PASS — treat prior as FAIL risk documented / partial. Use FAIL from bug list.
prev["BUG-05"] = "FAIL"  # was open risk P2 in bug list

def status_of(bug_id):
    if bug_id == "BUG-03":
        return by["BUG-03"]["Status"]
    if bug_id == "BUG-10":
        return by["BUG-10"]["Status"]
    r = by.get(bug_id)
    if not r:
        return "NOT RUN"
    return r["Status"]

now = datetime.now()
stamp = now.strftime("%Y%m%d-%H%M")
now_label = now.strftime("%Y-%m-%d %H:%M")

rows = []
for bug in [f"BUG-{i:02d}" for i in range(1, 11)]:
    old = prev[bug]
    new = status_of(bug)
    if new == "PASS" and old == "FAIL":
        verdict = "ĐÃ SỬA"
    elif new == "FAIL" and old == "FAIL":
        verdict = "VẪN LỖI"
    elif new == "PASS" and old == "PASS":
        verdict = "VẪN OK"
    elif new == "BLOCKED":
        verdict = "CHƯA XÁC MINH LẠI (bị chặn)"
    elif new == "FAIL" and old == "PASS":
        verdict = "HỒI QUY MỚI"
    else:
        verdict = f"{old} → {new}"
    detail = by.get(bug, by.get(bug + "a", {})).get("Actual", "")
    if bug == "BUG-03":
        detail = by["BUG-03"]["Actual"]
    if bug == "BUG-10":
        detail = by["BUG-10"]["Actual"]
    rows.append((bug, old, new, verdict, detail))

table_bugs = "\n".join(
    f"| {b} | {o} | {n} | {v} | {(d or '').replace('|','/')[:100]} |"
    for b, o, n, v, d in rows
)

smoke_ids = [r for r in results if r["ID"].startswith("SMOKE-") or r["ID"].startswith("REG-")]
smoke_table = "\n".join(
    f"| {r['ID']} | {(r.get('Fn') or '')[:40]} | {r['Status']} | {(r.get('Actual') or '').replace('|','/')[:110]} |"
    for r in sorted(smoke_ids, key=lambda x: x["ID"])
)

case_table = "\n".join(
    f"| {r['ID']} | {(r.get('Fn') or '').replace('|','/')[:40]} | {(r.get('Expected') or '').replace('|','/')[:50]} | {(r.get('Actual') or '').replace('|','/').replace(chr(10),' ')[:100]} | {r['Status']} |"
    for r in results
)

fixed = [b for b, o, n, v, _ in rows if v == "ĐÃ SỬA"]
still = [b for b, o, n, v, _ in rows if v == "VẪN LỖI"]
blocked = [b for b, o, n, v, _ in rows if "CHƯA XÁC MINH" in v]
new_regs = ["REG-NEW-01 (login 500 Redis auth)", "REG-NEW-02 (worker crash loop)", "REG-NEW-03 (checkout 500)"]

report = f"""# Báo cáo kiểm thử lại (regression) — PS_project

- Thời gian: {now_label} (Asia/Saigon)
- So với báo cáo trước: `test-reports/bao-cao-kiem-thu-2026-10-21.md`
- Project: `D:\\code\\PS_project`
- Phạm vi: BUG-01..BUG-10 + smoke luồng chính; không sửa code, không xóa dữ liệu thật
- Tài khoản owner demo dùng để thử (mật khẩu không ghi vào báo cáo)
- Bằng chứng JSON: `test-reports/retest-results.json`

## 1. Tổng quan lần chạy lại

Docker đang chạy. Redis đã bật `requirepass` (tiến bộ bảo mật) nhưng **API và worker không kết nối được Redis** → `redis.exceptions.AuthenticationError` → **login/checkout trả 500**, worker restart liên tục. Một số bug bảo mật đã vá được; đồng thời xuất hiện hồi quy P0 chặn gần như mọi luồng có session/Redis.

## 2. Tổng số test case (lần này)

| Trạng thái | Số lượng |
|-----------|---------|
| PASS | {cnt.get("PASS", 0)} |
| FAIL | {cnt.get("FAIL", 0)} |
| BLOCKED | {cnt.get("BLOCKED", 0)} |
| NOT RUN | {cnt.get("NOT RUN", 0)} |
| **Tổng** | **{len(results)}** |

## 3. So sánh BUG-01 .. BUG-10 với lần trước

| Bug | Trước | Nay | Kết luận | Bằng chứng rút gọn |
|-----|-------|-----|----------|-------------------|
{table_bugs}

### Chi tiết từng bug

**BUG-01 GHN webhook không chữ ký — ĐÃ SỬA**  
`POST /api/v1/webhooks/ghn` không chữ ký → **401** `Missing webhook signature`.

**BUG-02 Khách tự confirm VietQR unpaid — CHƯA XÁC MINH LẠI**  
Bị chặn vì login 500 (không tạo được session để checkout VietQR + confirm).

**BUG-03 Postgres/Redis lộ cổng + Redis không mật khẩu — VẪN LỖI (một phần đã tốt)**  
- Redis **đã** `requirepass`: PING không AUTH bị từ chối (`6379_pong=False`).  
- Cổng host **vẫn mở**: 5432, 6379, 6380.  
- Hồi quy: app chưa dùng mật khẩu Redis đúng cách → login/worker gãy.

**BUG-04 Cart qty > stock — CHƯA XÁC MINH LẠI**  
Cần login + CSRF; login đang 500.

**BUG-05 Nginx 502 sau recreate Next.js — ĐÃ ỔN Ở HIỆN TẠI**  
nginx :80 FE+API trả 200. Rủi ro recreate vẫn nên theo dõi.

**BUG-06 SĐT không hợp lệ — ĐÃ SỬA**  
phone `12ab34cd56` → **422** “Số điện thoại không hợp lệ”.

**BUG-07 Thiếu security headers — ĐÃ SỬA**  
FE :3000 và nginx :80 đều có đủ CSP, X-Frame-Options, X-Content-Type-Options, HSTS, Referrer-Policy.

**BUG-08 `/admin` shell khi chưa login — VẪN LỖI**  
`GET /admin` vẫn 200, body ~11KB. Admin API anon vẫn 401 (ổn).

**BUG-09 `full_name` HTML thô — ĐÃ SỬA**  
Đăng ký với payload XSS → 201 và **không** còn thẻ `<img` thô trong response (đã sanitize/strip).

**BUG-10 Ruff/mypy/pytest nghèo — VẪN LỖI**  
ruff **132** lỗi (trước 130), mypy **15** lỗi, pytest encryption **1 passed**; vẫn thiếu suite API.

## 4. Hồi quy / lỗi mới

| ID | Mức | Mô tả |
|----|-----|------|
| REG-NEW-01 | **P0** | `POST /api/v1/auth/login` → **500**. Log: Redis `AuthenticationError: Authentication required` trong `enforce_rate_limit`. |
| REG-NEW-02 | **P0** | `fastapi-worker` restart loop cùng lỗi Redis auth. |
| REG-NEW-03 | **P0** | Guest COD checkout → **500** (phụ thuộc Redis/idempotency/rate-limit). |

Nguyên nhân khả dĩ (chưa khẳng định root-cause tuyệt đối): Redis đã bật `--requirepass` từ compose, trong khi URL Redis của API/worker trên container **không mang credential** (env chỉ thấy `REDIS_*_URL`, không thấy password được inject vào kết nối). Kết quả: vá BUG-03 một phần nhưng làm gãy auth và worker.

## 5. Smoke luồng chính

| Test ID | Chức năng | Status | Thực tế |
|---------|-----------|--------|---------|
{smoke_table}

- Home FE + nginx: **PASS**
- Products: **PASS**
- Login customer/owner, cart, COD checkout, track, owner reads: **FAIL/BLOCKED** do Redis auth

## 6. Phần chưa test lại được

- BUG-02, BUG-04 và toàn bộ luồng cần cookie session (cart, confirm, owner API) — chặn bởi login 500
- UI click Playwright / ESLint — vẫn chưa có trong project (như lần trước)

## 7. Đề xuất ưu tiên ngay

1. **P0:** Sửa kết nối Redis của API + worker (URL có password hoặc truyền password vào client) rồi restart service; xác nhận login + worker healthy  
2. Chạy lại BUG-02, BUG-04, smoke cart/checkout/owner  
3. Cân nhắc không publish 5432/6379/6380 ra `0.0.0.0`  
4. FE guard `/admin` khi chưa đăng nhập  
5. Tiếp tục giảm nợ ruff/mypy + thêm pytest API

## 8. Kết luận sẵn sàng

**Xấu hơn lần trước về khả năng dùng app** dù một số bug bảo mật (GHN chữ ký, SĐT, headers, sanitize tên, Redis password) đã tiến bộ.

**Verdict: chưa sẵn sàng** — thậm chí **local demo đang gãy login/checkout**. Vá hồi quy Redis trước, rồi mới đánh giá lại readiness.

### Tóm tắt nhanh BUG

- **Đã sửa:** {', '.join(fixed) if fixed else '(không)'}
- **Vẫn lỗi:** {', '.join(still) if still else '(không)'}
- **Chưa xác minh lại (blocked):** {', '.join(blocked) if blocked else '(không)'}
- **Mới / hồi quy:** {'; '.join(new_regs)}

---

## Phụ lục — Bảng test case lần này

| Test ID | Chức năng | Mong đợi | Thực tế | Status |
|---------|-----------|----------|---------|--------|
{case_table}
"""

out = REPORT_DIR / f"bao-cao-kiem-thu-lai-{stamp}.md"
out.write_text(report, encoding="utf-8")
print("REPORT", out)
print("COUNTS", dict(cnt), "TOTAL", len(results))
print("FIXED", fixed)
print("STILL", still)
print("BLOCKED_BUGS", blocked)
print("STAMP", stamp)
