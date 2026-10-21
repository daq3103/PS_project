# Báo cáo kiểm thử full-stack — PS_project

- Thời gian: 2026-10-21 08:52 (Asia/Saigon)
- Project: `D:\code\PS_project`
- App: http://localhost:3000 (Next.js), API http://localhost:8000 (FastAPI), nginx :80
- Môi trường: Docker Compose trên máy Windows (MSI)
- Tài khoản test: owner demo `owner@demo.com` (mật khẩu không ghi vào báo cáo); các tài khoản QA tự tạo `qa.user1.*`, `qa.user2.*`, `qa.xss.*`
- Phạm vi: không sửa code production, không xóa dữ liệu thật, chỉ đụng dữ liệu QA tự tạo

## 1. Tổng quan hệ thống đã kiểm thử

Cửa hàng thú cưng (pet shop) full-stack:

- Frontend: Next.js 15 + React 19 + Tailwind (container `ps_project-nextjs-1`)
- Backend: FastAPI + SQLAlchemy async + Alembic (`ps_project-fastapi-api-1`, worker arq)
- DB: Postgres/pgvector cổng host 5432
- Redis cache 6379, Redis queue 6380 (không mật khẩu)
- Auth: cookie HttpOnly `access_token` / `refresh_token` + CSRF double-submit
- Thanh toán: COD (tự xác nhận), VietQR (pending đến khi webhook)
- Vận chuyển: mock GHN webhook

Luồng chính đã kiểm thử: đăng ký/đăng nhập, địa chỉ, sản phẩm/giỏ, checkout guest+user (COD/VietQR), theo dõi đơn, admin owner, webhook GHN, header bảo mật, cổng DB/Redis.

## 2. Môi trường và phạm vi

| Hạng mục | Chi tiết |
|---------|----------|
| FE | localhost:3000, nginx :80 |
| BE | localhost:8000 OpenAPI `/api/v1/*` |
| DB/Redis | publish ra host, Redis không auth |
| Công cụ | Python HTTP, docker exec, ruff/mypy/pytest trong container, tsc trên host |
| Không làm | Stress test, sửa code, xóa data seed, Playwright E2E, ESLint (chưa cấu hình) |

## 3. Tổng số test case

| Trạng thái | Số lượng |
|-----------|---------|
| PASS | 39 |
| FAIL | 14 |
| BLOCKED | 0 |
| NOT RUN | 4 |
| **Tổng** | **57** |

## 4. Danh sách bug theo mức nghiêm trọng

### P1 — High

**BUG-01 — Webhook GHN không kiểm chữ ký**

- Severity/Priority: P1
- Endpoint: `POST /api/v1/webhooks/ghn`
- Bước: gửi JSON tùy ý, không header chữ ký → HTTP 200 (`ignored`/`ok`), vẫn ghi `webhook_events`
- Expected: 401/403 nếu thiếu/sai chữ ký (VietQR có `X-Signature`)
- Actual: chấp nhận không chữ ký; nếu `tracking_code` khớp fulfillment có thể đẩy đơn sang `delivered`
- Ảnh hưởng: giả mạo trạng thái giao hàng
- File: `backend/app/modules/shipping/router.py`
- Đề xuất: thêm HMAC/secret; từ chối khi thiếu

**BUG-02 — Khách tự xác nhận đơn VietQR chưa thanh toán**

- Severity/Priority: P1
- Tiền điều kiện: đăng nhập, checkout `payment_method=vietqr` → `pending` + `unpaid`
- Bước: `POST /api/v1/orders/{id}/confirm` bằng chính customer
- Expected: chỉ staff hoặc bắt buộc đã thanh toán
- Actual: 200, status → `confirmed` dù `payment_status=unpaid` (order_code `8X88B4RX3Z`)
- Ảnh hưởng: bỏ qua thanh toán, kho/đóng gói có thể xử lý đơn chưa trả tiền
- File: `backend/app/modules/order/router.py` (`confirm_order` cho phép actor customer)
- Đề xuất: chặn customer confirm, hoặc bắt buộc `payment_status=paid` với VietQR

### P2 — Medium

**BUG-03 — Postgres/Redis publish ra host + Redis không mật khẩu**

- Severity: P2 (local); cao hơn nếu expose LAN/tunnel
- Bằng chứng: localhost `5432`/`6379`/`6380` mở; `redis-cli ping` → PONG không AUTH
- Đề xuất: bind `127.0.0.1` hoặc bỏ publish; bật `requirepass`

**BUG-04 — Giỏ hàng cho phép số lượng vượt tồn**

- Bước: `POST /api/v1/cart/items` qty=99 khi `cached_available_qty=50` → 200
- Expected: 400/409
- Đề xuất: validate tồn lúc add/update cart và lúc checkout

**BUG-05 — Nguy cơ 502 nginx sau khi recreate Next.js**

- Hiện tại nginx/FE đang 200; phiên trước gặp 502 khi nextjs rebuild đổi IP còn nginx giữ upstream cũ
- Đề xuất: proxy theo tên service Docker, reload nginx khi upstream đổi

### P3 — Low

**BUG-06 — Đăng ký chấp nhận SĐT không hợp lệ** (`12ab34cd56` → 201)

**BUG-07 — Thiếu security headers trên FE** (CSP, X-Frame-Options, X-Content-Type-Options, HSTS, Referrer-Policy)

**BUG-08 — `/admin` trả HTML khi chưa đăng nhập** (API vẫn 401/403)

**BUG-09 — `full_name` lưu HTML thô trong DB/API** (FE React text đang escape nên chưa XSS được trên UserMenu)

**BUG-10 — Ruff 130 lỗi, mypy 15 lỗi; gần như không có pytest nghiệp vụ** (chỉ `test_encryption.py` pass)

## 5. Luồng nghiệp vụ hoạt động tốt

- Health/Ready, list categories/products
- Đăng ký/đăng nhập cookie+CSRF, logout
- Address CRUD của chính mình; IDOR địa chỉ bị chặn (404)
- Guest checkout COD + `/orders/track` (che SĐT/địa chỉ)
- Customer checkout COD; xem đơn của mình; IDOR đơn bị 403
- Owner: dashboard/orders/lots; customer bị chặn admin (403)
- Admin API anonymous 401
- Nginx proxy FE+API hiện ổn
- `tsc --noEmit` PASS

## 6. Chức năng chưa test được và lý do

| Hạng mục | Lý do |
|---------|-------|
| ESLint / next lint | Chưa cấu hình ESLint; lệnh mở wizard tương tác |
| Playwright E2E / UI click đầy đủ | Không có Playwright trong project |
| Responsive / console browser | Không chạy automation trình duyệt phiên này |
| Pack/ship/GHN delivered end-to-end | Tránh đụng đơn thật/seed; webhook unsigned đã test riêng |
| TOTP admin enroll/verify | Không có secret TOTP |
| Upload ảnh sản phẩm, promotion ghi | Tránh đổi catalog |
| pytest API rộng | Repo gần như không có suite |

## 7. Rủi ro còn tồn tại

- Webhook GHN giả mạo (P1) nếu có tracking thật
- Khách confirm VietQR unpaid (P1)
- Redis/Postgres lộ cổng khi tunnel/LAN
- Cart overstock → lệch kỳ vọng tồn đến lúc checkout
- 502 sau deploy FE nếu nginx không theo DNS
- Thiếu E2E và lint FE → hồi quy UI dễ lọt

## 8. Đề xuất ưu tiên sửa

1. Ký và xác thực webhook GHN (và rà soát mọi webhook)
2. Chặn customer confirm / bắt buộc đã thanh toán với VietQR
3. Khóa cổng DB/Redis + mật khẩu Redis
4. Validate tồn kho trên cart
5. Security headers + sanitize `full_name` + FE guard `/admin`
6. Ổn định upstream nginx; bổ sung pytest API + ESLint/Playwright

## 9. Test cần chạy lại sau khi sửa

- SEC-GHN-01, ORD-SELFCONF-01, CART-OVER-01, SEC-PORT-*, SEC-REDIS-01, SEC-HDR-01, VAL-PHONE-01, SEC-XSS-*, SEC-ADMIN-01
- Regression: checkout COD/VietQR, track đơn, address IDOR, owner dashboard
- Sau khi có Playwright: login owner → admin pack/ship; guest checkout UI

## 10. Kết luận mức độ sẵn sàng

**Chưa sẵn sàng production/public demo.** Các luồng mua COD cơ bản và admin đọc dữ liệu chạy được, nhưng còn lỗi P1 (webhook GHN không chữ ký; khách tự confirm đơn VietQR chưa trả tiền) và cấu hình hạ tầng kém an toàn (Redis/Postgres mở, thiếu header). Phù hợp tiếp tục phát triển local; cần vá P1 trước khi mở ra ngoài.

---

## Phụ lục A — Bảng test case

| Test ID | Chức năng | Mong đợi | Thực tế (rút gọn) | Status |
|---------|-----------|----------|-------------------|--------|
| ADDR-01 | Create address | 201 | 201 {"id":"69b3558a-5178-44e1-8007-6d88cb4bc5cb","recipient_name":"QA Addr One","recipient_phone":"0901234567","province | PASS |
| ADDR-02 | List addresses | 200 | 200 [{"id":"69b3558a-5178-44e1-8007-6d88cb4bc5cb","recipient_name":"QA Addr One","recipient_phone":"0901234567","provinc | PASS |
| ADDR-03 | Update address | 200 | 200 {"id":"69b3558a-5178-44e1-8007-6d88cb4bc5cb","recipient_name":"QA Addr One","recipient_phone":"0901234567","province | PASS |
| ADDR-04 | Delete own addr | 200/204 | 204  | PASS |
| AUTH-LOGIN-01 | Login user1 | 200 | 200 cookies=['access_token', 'refresh_token', 'csrf_token'] | PASS |
| AUTH-LOGIN-02 | Login user2 | 200 | 200 cookies=['access_token', 'refresh_token', 'csrf_token'] | PASS |
| AUTH-LOGOUT-01 | Logout | 200 | 204  | PASS |
| AUTH-ME-01 | GET /me anonymous | 200 with user null (guest session) | 200 user=null csrf+guest issued | PASS |
| AUTH-ME-02 | GET /me user1 | 200 | 200 {"user":{"id":"fa1eff9f-53bf-4a88-9ef7-756de761a2e8","email":"qa.user1.1792547004@example.com","phone":"0911547004", | PASS |
| AUTH-OWNER-01 | Login owner | 200 | 200 role check {"id":"2b30a4ef-39eb-498e-99e6-cb2e7964c94b","email":"owner@demo.com","phone":null,"full_name":"Owner Dem | PASS |
| AUTH-REG-01 | Register user1 | 201 | 201 {"id":"fa1eff9f-53bf-4a88-9ef7-756de761a2e8","email":"qa.user1.1792547004@example.com","phone":"0911547004","full_na | PASS |
| AUTH-REG-02 | Register user2 | 201 | 201 {"id":"1ebf5a05-be4c-4580-bde0-9e184a1f021c","email":"qa.user2.1792547004@example.com","phone":"0912547004","full_na | PASS |
| CART-OVER-01 | Add qty>stock | reject | 200 stock~50 qty=99 {"id":"a50a073f-1953-4a2a-b3fc-62d14592c6af","items":[{"id":"b01d91e0-0670-4f5d-9619-c2280f1f21f3"," | FAIL |
| CAT-01 | Categories | 200 | 200 [{"id":"8243b08d-c40d-414a-b8b4-440f928d8342","parent_id":null,"name":"Thức ăn h | PASS |
| CHK-GUEST-01 | Guest checkout COD | 201 | 201 {"id":"6dcdba34-a3da-4f5a-b8f5-3c8044c48bee","order_code":"9RHOSTVS8P","status":"confirmed","payment_method":"cod"," | PASS |
| CHK-USER-01 | Customer checkout | 201 | 201 {"id":"5a18d9f5-34a5-4449-9cc0-830c7e3c0642","order_code":"KETHJJMRHF","status":"confirmed","payment_method":"cod"," | PASS |
| ENV-01 | Healthz | 200 | 200 {"status":"ok"} | PASS |
| ENV-02 | Readyz | 200 | 200 {"status":"ready"} | PASS |
| FE-LINT-01 | next lint / ESLint | lint clean | eslint not configured; next lint interactive wizard | NOT RUN |
| FE-PW-01 | Playwright E2E | e2e pass | playwright not installed | NOT RUN |
| FE-TSC-01 | TypeScript tsc --noEmit | 0 errors | exit 0 | PASS |
| INT-502-01 | Nginx 502 after nextjs recreate | stable now; known risk | current 200; prior session 502 after rebuild | PASS |
| INT-NGINX-01 | Nginx root proxy | 200 | 200 len=29576 | PASS |
| INT-NGINX-02 | Nginx API proxy | 200 | 200 [{"id":"8243b08d-c40d-414a-b8b4-440f928d8342","parent_id":null,"name":"Thức ăn h | PASS |
| ORD-GUEST-01 | Anonymous GET /orders/{id} | 403; guest uses /orders/track instead | 403 denied; track 200 masked | PASS |
| ORD-OWN-01 | Customer GET own order | 200 | 200 {"id":"5a18d9f5-34a5-4449-9cc0-830c7e3c0642","order_code":"KETHJJMRHF","status":"confirmed","payment | PASS |
| ORD-SELFCONF-01 | Customer self-confirm unpaid VietQR | staff-only or require paid | 200 confirmed unpaid vietqr pending->confirmed | FAIL |
| ORD-TRACK-01 | Track guest order | 200 | 200 {"order_code":"9RHOSTVS8P","status":"confirmed","payment_status":"unpaid","total_amount":119000,"customer_name":"QA  | PASS |
| OWN-01 | Owner dashboard | 200 | 200 {"orders_today":0,"revenue_today":0,"pending_orders":0,"pending_reviews":3,"drift_count":0,"out_of_stock_variants":0 | PASS |
| OWN-02 | Owner orders | 200 | 200 [{"id":"0b95f40c-c491-46dd-b9c8-66ba53c5aff6","order_code":"W3KLNK17RW","status":"packed","payment_method":"cod","pa | PASS |
| OWN-03 | Owner lots | 200 | 200 [{"id":"07aa5c08-acde-4647-9b58-0ddd066e0c05","variant_id":"b8a5445a-74c3-475c-9d0b-d14a2a9c0e09","lot_no":"SEED-001 | PASS |
| PROD-01 | List products | 200 | 200 [{"id":"cbf718ae-077c-4141-b825-5cef5f1a5162","category_id":"3996fff7-8a31-4dd7-a7cd-d21dcc946258","name":"Vòng cổ n | PASS |
| PROD-02 | Resolve variant | variant | v=e0369daf-9ce5-4769-b91d-d6734d4a46df stock=None prod=cbf718ae-077c-4141-b825-5cef5f1a5162 | PASS |
| SEC-ADMIN-01 | Admin UI anon | block UI | 200 len=8927 | FAIL |
| SEC-ADMIN-02 | Admin API anon | 401/403 | 401 {"detail":"Authentication required"} | PASS |
| SEC-AUTHZ-01 | Customer admin dash | 403 | 403 {"detail":"Staff access required"} | PASS |
| SEC-GHN-01 | GHN unsigned | 401/403 | 200 {"status":"ignored","reason":"fulfillment_not_found"} | FAIL |
| SEC-HDR-01 | FE security headers | CSP/XFO/XCTO/HSTS/RP | missing=['Content-Security-Policy', 'X-Frame-Options', 'X-Content-Type-Options', 'Strict-Transport-Security', 'Referrer- | FAIL |
| SEC-IDOR-01 | User2 PATCH user1 addr | 403/404 | 404 {"detail":"Địa chỉ không tồn tại"} | PASS |
| SEC-IDOR-02 | User2 DELETE user1 addr | 403/404 | 404 {"detail":"Địa chỉ không tồn tại"} | PASS |
| SEC-IDOR-03 | User2 confirm user1 | 403 | 403 {"detail":"Không có quyền"} | PASS |
| SEC-IDOR-04 | User2 GET user1 order | 403/404 | 403 {"detail":"Không có quyền xem đơn"} | PASS |
| SEC-PORT-01 | Postgres 5432 | not published | open=True | FAIL |
| SEC-PORT-02 | Redis 6379 | not published | open=True | FAIL |
| SEC-PORT-03 | Redis 6380 | not published | open=True | FAIL |
| SEC-REDIS-01 | Redis no password | requirepass | ping PONG no AUTH | FAIL |
| SEC-XSS-01 | Register XSS name | reject/accept | 201 {"id":"e923ac73-ccb3-4503-8b55-fb87290854bb","email":"qa.xss.1792547004@example.com","phone":"0903547004","full_name | PASS |
| SEC-XSS-02 | XSS name FE render | FE escapes text nodes | API stores raw HTML; UserMenu uses React text escape; no dangerouslySetInnerHTML | PASS |
| SEC-XSS-03 | Stored XSS risk in DB/API | sanitize on write | full_name stored with HTML tags in DB/API | FAIL |
| TOOL-MYPY-01 | mypy app (container) | 0 errors | 15 errors in 6 files | FAIL |
| TOOL-PYTEST-01 | pytest encryption in container | pass | 1 passed test_encryption.py | PASS |
| TOOL-PYTEST-02 | pytest suite completeness | meaningful suite | only encryption unit test; no API/E2E suite | FAIL |
| TOOL-RUFF-01 | ruff check app (container) | 0 errors | 130 errors (B008,E501,F401,F821,...) | FAIL |
| UI-ADMIN-01 | Admin UI login flow | owner uses /admin after login | API owner PASS; UI click-through not automated | NOT RUN |
| UI-HOME-01 | Home page loads | 200 | 200 len=29576 | PASS |
| UI-RESP-01 | Responsive UI manual | ok mobile/tablet | no browser automation this session | NOT RUN |
| VAL-PHONE-01 | Invalid phone letters | 400/422 | 201 {"id":"9e8a4168-4cfc-4527-bb38-dc0c1050ddaa","email":"qa.badphone3.1792547004@example.com","phone":"12ab34cd56","ful | FAIL |

## Phụ lục B — Ghi chú bằng chứng

- Raw JSON: `test-reports/api-results.json`
- Đơn QA tạo trong phiên: guest `9RHOSTVS8P`, user COD `KETHJJMRHF`, VietQR self-confirm `8X88B4RX3Z`
- Không ghi mật khẩu vào báo cáo
