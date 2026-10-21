import json
from pathlib import Path
from collections import Counter
from datetime import datetime

p = Path(r"D:\code\PS_project\test-reports")
R = json.loads((p / "api-results.json").read_text(encoding="utf-8"))
by = {x["ID"]: x for x in R}

def upsert(i, f, s, e, a, ev=""):
    by[i] = dict(ID=i, Fn=f, Status=s, Expected=e, Actual=a, Evidence=ev)

upsert("AUTH-ME-01", "GET /me anonymous", "PASS", "200 with user null (guest session)", "200 user=null csrf+guest issued", "by design")
upsert("ORD-GUEST-01", "Anonymous GET /orders/{id}", "PASS", "403; guest uses /orders/track instead", "403 denied; track 200 masked", "recheck after flaky 404")
upsert("ORD-SELFCONF-01", "Customer self-confirm unpaid VietQR", "FAIL", "staff-only or require paid", "200 confirmed unpaid vietqr pending->confirmed", "P1 business bug")
upsert("SEC-XSS-02", "XSS name FE render", "PASS", "FE escapes text nodes", "API stores raw HTML; UserMenu uses React text escape; no dangerouslySetInnerHTML", "stored unsanitized but FE safe")
upsert("SEC-XSS-03", "Stored XSS risk in DB/API", "FAIL", "sanitize on write", "full_name stored with HTML tags in DB/API", "defense in depth")
upsert("TOOL-RUFF-01", "ruff check app (container)", "FAIL", "0 errors", "130 errors (B008,E501,F401,F821,...)", "temp install in container")
upsert("TOOL-MYPY-01", "mypy app (container)", "FAIL", "0 errors", "15 errors in 6 files", "")
upsert("TOOL-PYTEST-01", "pytest encryption in container", "PASS", "pass", "1 passed test_encryption.py", "tests not in image; host copy")
upsert("TOOL-PYTEST-02", "pytest suite completeness", "FAIL", "meaningful suite", "only encryption unit test; no API/E2E suite", "")
upsert("FE-TSC-01", "TypeScript tsc --noEmit", "PASS", "0 errors", "exit 0", "")
upsert("FE-LINT-01", "next lint / ESLint", "NOT RUN", "lint clean", "eslint not configured; next lint interactive wizard", "no eslint dep")
upsert("FE-PW-01", "Playwright E2E", "NOT RUN", "e2e pass", "playwright not installed", "")
upsert("UI-RESP-01", "Responsive UI manual", "NOT RUN", "ok mobile/tablet", "no browser automation this session", "")
upsert("UI-ADMIN-01", "Admin UI login flow", "NOT RUN", "owner uses /admin after login", "API owner PASS; UI click-through not automated", "")
upsert("INT-502-01", "Nginx 502 after nextjs recreate", "PASS", "stable now; known risk", "current 200; prior session 502 after rebuild", "regression risk P2")

results = sorted(by.values(), key=lambda x: x["ID"])
(p / "api-results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
cnt = Counter(x["Status"] for x in results)

now = datetime.now().strftime("%Y-%m-%d %H:%M")
L = []
a = L.append
a("# Bao cao kiem thu full-stack — PS_project")
a("")
a(f"- Thoi gian: {now} (Asia/Saigon)")
a("- Project: D:\\code\\PS_project")
a("- App: http://localhost:3000 (Next.js), API http://localhost:8000 (FastAPI), nginx :80")
a("- Moi truong: Docker Compose tren may Windows (MSI)")
a("- Tai khoan test: owner demo owner@demo.com (mat khau KHONG ghi vao bao cao); QA tu tao qa.user1.*, qa.user2.*, qa.xss.*")
a("- Pham vi: khong sua code production, khong xoa du lieu that, chi dung du lieu QA tu tao")
a("")
a("## 1. Tong quan he thong da kiem thu")
a("")
a("Cua hang thu cung (pet shop) full-stack:")
a("- Frontend: Next.js 15 + React 19 + Tailwind (container ps_project-nextjs-1)")
a("- Backend: FastAPI + SQLAlchemy async + Alembic (ps_project-fastapi-api-1, worker arq)")
a("- DB: Postgres/pgvector cong host 5432")
a("- Redis cache 6379, Redis queue 6380 (khong mat khau)")
a("- Auth: cookie HttpOnly access_token/refresh_token + CSRF double-submit")
a("- Thanh toan: COD (tu xac nhan), VietQR (pending den webhook)")
a("- Van chuyen: mock GHN webhook")
a("")
a("Luong chinh da test: dang ky/dang nhap, dia chi, san pham/gio, checkout guest+user (COD/VietQR), theo doi don, admin owner, webhook GHN, header bao mat, cong DB/Redis.")
a("")
a("## 2. Moi truong va pham vi")
a("")
a("| Hang muc | Chi tiet |")
a("|---------|----------|")
a("| FE | localhost:3000, nginx :80 |")
a("| BE | localhost:8000 OpenAPI /api/v1/* |")
a("| DB/Redis | publish ra host, Redis khong auth |")
a("| Cong cu | Python HTTP, docker exec, ruff/mypy/pytest container, tsc host |")
a("| Khong lam | Stress, sua code, xoa data seed, Playwright E2E, ESLint (chua cau hinh) |")
a("")
a("## 3. Tong so test case")
a("")
a("| Trang thai | So luong |")
a("|-----------|---------|")
for k in ["PASS", "FAIL", "BLOCKED", "NOT RUN"]:
    a(f"| {k} | {cnt.get(k, 0)} |")
a(f"| **Tong** | **{len(results)}** |")
a("")
a("## 4. Danh sach bug theo muc nghiem trong")
a("")
a("### P1 — High")
a("")
a("**BUG-01 — Webhook GHN khong kiem chu ky**")
a("- Severity/Priority: P1")
a("- Endpoint: POST /api/v1/webhooks/ghn")
a("- Buoc: gui JSON tuy y khong header chu ky -> HTTP 200 (ignored/ok), van ghi webhook_events")
a("- Expected: 401/403 neu thieu/sai chu ky (VietQR co X-Signature)")
a("- Actual: chap nhan khong chu ky; neu tracking_code khop fulfillment co the day don delivered")
a("- Anh huong: gia mao trang thai giao hang")
a("- File: backend/app/modules/shipping/router.py")
a("- De xuat: HMAC/secret + tu choi khi thieu")
a("")
a("**BUG-02 — Khach tu xac nhan don VietQR chua thanh toan**")
a("- Severity/Priority: P1")
a("- Tien dieu kien: login, checkout payment_method=vietqr -> pending unpaid")
a("- Buoc: POST /api/v1/orders/{id}/confirm bang chinh customer")
a("- Expected: chi staff hoac bat buoc da thanh toan")
a("- Actual: 200, status confirmed du payment_status=unpaid (order_code 8X88B4RX3Z)")
a("- Anh huong: bo qua thanh toan")
a("- File: backend/app/modules/order/router.py (confirm_order cho phep actor customer)")
a("- De xuat: chan customer confirm, hoac bat payment_status=paid voi VietQR")
a("")
a("### P2 — Medium")
a("")
a("**BUG-03 — Postgres/Redis publish ra host + Redis khong mat khau**")
a("- Severity: P2 (local); cao hon neu expose LAN/tunnel")
a("- Bang chung: localhost 5432/6379/6380 mo; redis-cli ping -> PONG khong AUTH")
a("- De xuat: bind 127.0.0.1 hoac bo publish; requirepass")
a("")
a("**BUG-04 — Gio hang cho phep qty vuot ton**")
a("- Buoc: POST /api/v1/cart/items qty=99 khi cached_available_qty=50 -> 200")
a("- Expected: 400/409")
a("- De xuat: validate ton luc add/update cart va checkout")
a("")
a("**BUG-05 — Nguy co 502 nginx sau recreate Next.js**")
a("- Hien tai nginx/FE 200; phien truoc gap 502 khi nextjs rebuild doi IP")
a("- De xuat: proxy theo ten service Docker, reload nginx khi upstream doi")
a("")
a("### P3 — Low")
a("")
a("**BUG-06 — Dang ky chap nhan SDT khong hop le** (phone 12ab34cd56 -> 201)")
a("**BUG-07 — Thieu security headers FE** (CSP, X-Frame-Options, X-Content-Type-Options, HSTS, Referrer-Policy)")
a("**BUG-08 — /admin tra HTML khi chua dang nhap** (API van 401/403)")
a("**BUG-09 — full_name luu HTML tho trong DB/API** (FE React text dang escape)")
a("**BUG-10 — Ruff 130 loi, mypy 15 loi; gan nhu khong co pytest nghiep vu**")
a("")
a("## 5. Luong nghiep vu hoat dong tot")
a("")
a("- Health/Ready, categories/products")
a("- Dang ky/dang nhap cookie+CSRF, logout")
a("- Address CRUD cua minh; IDOR dia chi bi chan (404)")
a("- Guest checkout COD + /orders/track (che SDT/dia chi)")
a("- Customer checkout COD; xem don cua minh; IDOR don 403")
a("- Owner dashboard/orders/lots; customer bi chan admin 403")
a("- Admin API anonymous 401")
a("- Nginx proxy FE+API hien on; tsc --noEmit PASS")
a("")
a("## 6. Chuc nang chua test duoc va ly do")
a("")
a("| Hang muc | Ly do |")
a("|---------|-------|")
a("| ESLint / next lint | Chua cau hinh; lenh mo wizard tuong tac |")
a("| Playwright E2E / UI click day du | Khong co Playwright |")
a("| Responsive / console browser | Khong chay automation trinh duyet phien nay |")
a("| Pack/ship/GHN delivered E2E | Tranh dung don that/seed |")
a("| TOTP admin | Khong co secret TOTP |")
a("| Upload anh / promotion ghi | Tranh doi catalog |")
a("| pytest API rong | Repo gan nhu khong co suite |")
a("")
a("## 7. Rui ro con ton tai")
a("")
a("- Webhook GHN gia mao (P1)")
a("- Khach confirm VietQR unpaid (P1)")
a("- Redis/Postgres lo cong khi tunnel/LAN")
a("- Cart overstock")
a("- 502 sau deploy FE")
a("- Thieu E2E va lint FE")
a("")
a("## 8. De xuat uu tien sua")
a("")
a("1. Ky va xac thuc webhook GHN")
a("2. Chan customer confirm / bat buoc da thanh toan VietQR")
a("3. Khoa cong DB/Redis + mat khau Redis")
a("4. Validate ton kho tren cart")
a("5. Security headers + sanitize full_name + FE guard /admin")
a("6. On dinh upstream nginx; bo sung pytest API + ESLint/Playwright")
a("")
a("## 9. Test can chay lai sau khi sua")
a("")
a("- SEC-GHN-01, ORD-SELFCONF-01, CART-OVER-01, SEC-PORT-*, SEC-REDIS-01, SEC-HDR-01, VAL-PHONE-01, SEC-XSS-*, SEC-ADMIN-01")
a("- Regression: checkout COD/VietQR, track don, address IDOR, owner dashboard")
a("- Sau khi co Playwright: login owner admin pack/ship; guest checkout UI")
a("")
a("## 10. Ket luan muc san sang")
a("")
a("**Chua san sang production/public demo.** Luong mua COD co ban va admin doc du lieu chay duoc, nhung con loi P1 (webhook GHN khong chu ky; khach tu confirm don VietQR chua tra tien) va ha tang kem an toan (Redis/Postgres mo, thieu header). Phu hop tiep tuc dev local; can va P1 truoc khi mo ra ngoai.")
a("")
a("---")
a("")
a("## Phu luc A — Bang test case")
a("")
a("| Test ID | Chuc nang | Mong doi | Thuc te (rut gon) | Status |")
a("|---------|-----------|----------|-------------------|--------|")
for x in results:
    act = (x.get("Actual") or "").replace("|", "/").replace("\n", " ")[:120]
    exp = (x.get("Expected") or "").replace("|", "/")[:60]
    fn = (x.get("Fn") or "").replace("|", "/")[:40]
    a(f"| {x['ID']} | {fn} | {exp} | {act} | {x['Status']} |")
a("")
a("## Phu luc B — Bang chung")
a("")
a("- Raw JSON: test-reports/api-results.json")
a("- Don QA: guest 9RHOSTVS8P, user COD KETHJJMRHF, VietQR self-confirm 8X88B4RX3Z")
a("- Khong commit mat khau")
a("")

# Vietnamese with diacritics version
report = """# Báo cáo kiểm thử full-stack — PS_project

- Thời gian: {now} (Asia/Saigon)
- Project: `D:\\code\\PS_project`
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
| PASS | {pass_n} |
| FAIL | {fail_n} |
| BLOCKED | {blocked_n} |
| NOT RUN | {notrun_n} |
| **Tổng** | **{total}** |

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
- Bước: `POST /api/v1/orders/{{id}}/confirm` bằng chính customer
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
{table}

## Phụ lục B — Ghi chú bằng chứng

- Raw JSON: `test-reports/api-results.json`
- Đơn QA tạo trong phiên: guest `9RHOSTVS8P`, user COD `KETHJJMRHF`, VietQR self-confirm `8X88B4RX3Z`
- Không ghi mật khẩu vào báo cáo
""".format(
    now=now,
    pass_n=cnt.get("PASS", 0),
    fail_n=cnt.get("FAIL", 0),
    blocked_n=cnt.get("BLOCKED", 0),
    notrun_n=cnt.get("NOT RUN", 0),
    total=len(results),
    table="\n".join(
        "| {id} | {fn} | {exp} | {act} | {st} |".format(
            id=x["ID"],
            fn=(x.get("Fn") or "").replace("|", "/")[:40],
            exp=(x.get("Expected") or "").replace("|", "/")[:60],
            act=(x.get("Actual") or "").replace("|", "/").replace("\n", " ")[:120],
            st=x["Status"],
        )
        for x in results
    ),
)

out = p / "bao-cao-kiem-thu-2026-10-21.md"
out.write_text(report, encoding="utf-8")
print("REPORT", out)
print("COUNTS", dict(cnt), "TOTAL", len(results))
for x in results:
    if x["Status"] == "FAIL":
        print("FAIL", x["ID"], x["Fn"][:60])
