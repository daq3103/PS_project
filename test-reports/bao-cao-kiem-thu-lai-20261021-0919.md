# Báo cáo kiểm thử lại (regression) — PS_project

- Thời gian: 2026-10-21 09:19 (Asia/Saigon)
- So với báo cáo trước: `test-reports/bao-cao-kiem-thu-2026-10-21.md`
- Project: `D:\code\PS_project`
- Phạm vi: BUG-01..BUG-10 + smoke luồng chính; không sửa code, không xóa dữ liệu thật
- Tài khoản owner demo dùng để thử (mật khẩu không ghi vào báo cáo)
- Bằng chứng JSON: `test-reports/retest-results.json`

## 1. Tổng quan lần chạy lại

Docker đang chạy. Redis đã bật `requirepass` (tiến bộ bảo mật) nhưng **API và worker không kết nối được Redis** → `redis.exceptions.AuthenticationError` → **login/checkout trả 500**, worker restart liên tục. Một số bug bảo mật đã vá được; đồng thời xuất hiện hồi quy P0 chặn gần như mọi luồng có session/Redis.

## 2. Tổng số test case (lần này)

| Trạng thái | Số lượng |
|-----------|---------|
| PASS | 15 |
| FAIL | 14 |
| BLOCKED | 7 |
| NOT RUN | 0 |
| **Tổng** | **36** |

## 3. So sánh BUG-01 .. BUG-10 với lần trước

| Bug | Trước | Nay | Kết luận | Bằng chứng rút gọn |
|-----|-------|-----|----------|-------------------|
| BUG-01 | FAIL | PASS | ĐÃ SỬA | 401 {"detail":"Missing webhook signature"} |
| BUG-02 | FAIL | BLOCKED | CHƯA XÁC MINH LẠI (bị chặn) | no variant/login |
| BUG-03 | FAIL | FAIL | VẪN LỖI | requirepass OK but 5432/6379/6380 still published on host |
| BUG-04 | FAIL | BLOCKED | CHƯA XÁC MINH LẠI (bị chặn) | no variant/login |
| BUG-05 | FAIL | PASS | ĐÃ SỬA | fe=200 api=200 [{"id":"8243b08d-c40d-414a-b8b4-440f928d8342","parent_id":nu |
| BUG-06 | FAIL | PASS | ĐÃ SỬA | 422 {"detail":[{"type":"value_error","loc":["body","phone"],"msg":"Value error, Số điện thoại không  |
| BUG-07 | FAIL | PASS | ĐÃ SỬA | fe_missing=[]; nginx_missing=[] |
| BUG-08 | FAIL | FAIL | VẪN LỖI | 200 len=11121 |
| BUG-09 | FAIL | PASS | ĐÃ SỬA | 201 no raw tag in response |
| BUG-10 | FAIL | FAIL | VẪN LỖI | ruff 132, mypy 15, only encryption pytest |

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
| REG-NEW-01 | Login broken after Redis requirepass | FAIL | 500 AuthenticationError: Redis auth required; API/worker cannot connect |
| REG-NEW-02 | Worker crash loop | FAIL | fastapi-worker Restarting; Redis AuthenticationError |
| REG-NEW-03 | Checkout COD guest | FAIL | 500 Internal Server Error |
| SMOKE-ADMIN-API-ANON | Admin API anon | PASS | 401 {"detail":"Authentication required"} |
| SMOKE-AUTHZ | authz | BLOCKED | owner login failed |
| SMOKE-CART | Add cart qty=1 | BLOCKED | no variant/login |
| SMOKE-COD | Guest COD checkout | FAIL | 500 Internal Server Error |
| SMOKE-HEALTH | Healthz | PASS | 200 {"status":"ok"} |
| SMOKE-HOME | Home FE :3000 | PASS | 200 len=29576 |
| SMOKE-LOGIN | Login customer | FAIL | 500 cookies=[] |
| SMOKE-NGINX | Home via nginx :80 | PASS | 200 len=29576 |
| SMOKE-OWN-DASH | dashboard | BLOCKED | owner login failed |
| SMOKE-OWN-ORDERS | orders | BLOCKED | owner login failed |
| SMOKE-OWNER-LOGIN | Login owner demo | FAIL | 500 role_ok=False |
| SMOKE-PRODUCTS | List products | PASS | 200 [{"id":"cbf718ae-077c-4141-b825-5cef5f1a5162","category_id":"3996fff7-8a31-4dd7- |
| SMOKE-READY | Readyz | PASS | 200 {"status":"ready"} |
| SMOKE-REG | Register customer | PASS | 201 {"id":"ebd48b1a-11e7-41fb-b258-b93ec424d517","email":"qa.retest.u1.1792548874@example.com","phone":"091354 |
| SMOKE-TRACK | Track guest order | BLOCKED | no order |
| SMOKE-VARIANT | Resolve variant+stock | PASS | v=067faa90-c423-4a0d-b792-ccdd67990ecd stock=49 |

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

- **Đã sửa:** BUG-01, BUG-05, BUG-06, BUG-07, BUG-09
- **Vẫn lỗi:** BUG-03, BUG-08, BUG-10
- **Chưa xác minh lại (blocked):** BUG-02, BUG-04
- **Mới / hồi quy:** REG-NEW-01 (login 500 Redis auth); REG-NEW-02 (worker crash loop); REG-NEW-03 (checkout 500)

---

## Phụ lục — Bảng test case lần này

| Test ID | Chức năng | Mong đợi | Thực tế | Status |
|---------|-----------|----------|---------|--------|
| BUG-01 | GHN webhook unsigned | 401/403 reject unsigned | 401 {"detail":"Missing webhook signature"} | PASS |
| BUG-02 | Customer self-confirm unpaid VietQR | reject | no variant/login | BLOCKED |
| BUG-03 | DB/Redis exposure + Redis auth | ports closed + requirepass | requirepass OK but 5432/6379/6380 still published on host | FAIL |
| BUG-03a | Postgres 5432 not published | not open on host | open=True | FAIL |
| BUG-03b | Redis 6379 not published | not open on host | open=True | FAIL |
| BUG-03c | Redis 6380 not published | not open on host | open=True | FAIL |
| BUG-03d | Redis requires auth | PING without AUTH fails | 6379_pong=False 6380_pong=False | PASS |
| BUG-04 | Cart qty > stock | reject | no variant/login | BLOCKED |
| BUG-05 | Nginx proxy stable (no 502 now) | 200 FE+API via nginx | fe=200 api=200 [{"id":"8243b08d-c40d-414a-b8b4-440f928d8342","parent_id":nu | PASS |
| BUG-06 | Register invalid phone | 400/422 | 422 {"detail":[{"type":"value_error","loc":["body","phone"],"msg":"Value error, Số điện thoại không  | PASS |
| BUG-07 | Security headers FE/nginx | CSP/XFO/XCTO/HSTS/RP on FE or nginx | fe_missing=[]; nginx_missing=[] | PASS |
| BUG-08 | Admin UI without login | redirect/block UI | 200 len=11121 | FAIL |
| BUG-09 | Sanitize full_name on write | strip HTML | 201 no raw tag in response | PASS |
| BUG-10 | Tooling overall (ruff/mypy/suite) | clean lint + meaningful suite | ruff 132, mypy 15, only encryption pytest | FAIL |
| BUG-10a | ruff check app | 0 errors | 132 errors (was 130) | FAIL |
| BUG-10b | mypy app | 0 errors | 15 errors in 6 files (same ballpark) | FAIL |
| BUG-10c | pytest encryption | pass | 1 passed | PASS |
| REG-NEW-01 | Login broken after Redis requirepass | 200 login | 500 AuthenticationError: Redis auth required; API/worker cannot connect | FAIL |
| REG-NEW-02 | Worker crash loop | worker healthy | fastapi-worker Restarting; Redis AuthenticationError | FAIL |
| REG-NEW-03 | Checkout COD guest | 201 | 500 Internal Server Error | FAIL |
| SMOKE-ADMIN-API-ANON | Admin API anon | 401/403 | 401 {"detail":"Authentication required"} | PASS |
| SMOKE-AUTHZ | authz | - | owner login failed | BLOCKED |
| SMOKE-CART | Add cart qty=1 | 200 | no variant/login | BLOCKED |
| SMOKE-COD | Guest COD checkout | 201 | 500 Internal Server Error | FAIL |
| SMOKE-HEALTH | Healthz | 200 | 200 {"status":"ok"} | PASS |
| SMOKE-HOME | Home FE :3000 | 200 HTML | 200 len=29576 | PASS |
| SMOKE-LOGIN | Login customer | 200 | 500 cookies=[] | FAIL |
| SMOKE-NGINX | Home via nginx :80 | 200 | 200 len=29576 | PASS |
| SMOKE-OWN-DASH | dashboard | - | owner login failed | BLOCKED |
| SMOKE-OWN-ORDERS | orders | - | owner login failed | BLOCKED |
| SMOKE-OWNER-LOGIN | Login owner demo | 200 role=owner | 500 role_ok=False | FAIL |
| SMOKE-PRODUCTS | List products | 200 | 200 [{"id":"cbf718ae-077c-4141-b825-5cef5f1a5162","category_id":"3996fff7-8a31-4dd7- | PASS |
| SMOKE-READY | Readyz | 200 | 200 {"status":"ready"} | PASS |
| SMOKE-REG | Register customer | 201 | 201 {"id":"ebd48b1a-11e7-41fb-b258-b93ec424d517","email":"qa.retest.u1.1792548874@example.com","phon | PASS |
| SMOKE-TRACK | Track guest order | 200 | no order | BLOCKED |
| SMOKE-VARIANT | Resolve variant+stock | have variant | v=067faa90-c423-4a0d-b792-ccdd67990ecd stock=49 | PASS |
