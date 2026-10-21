# Kế hoạch triển khai hệ thống — theo thiết kế v1.3

> Dựa trên tài liệu `thiet-ke-he-thong-v1.3.docx` (cập nhật 19/10/2026). Plan này xếp ưu tiên theo 3 nhóm khuyến nghị từ review: **Nhóm A — chốt trước khi code**, **Nhóm B — hoàn thiện trước go-live**, **Nhóm C — sau go-live**.

## 0. Nguyên tắc ưu tiên

| Nhóm | Nội dung | Xử lý ở |
|---|---|---|
| A — Chốt trước khi code | Spec auth/session (JWT rotation, CSRF, 2FA), pattern commit→enqueue→idempotent (mục 4.4), schema v1.3 (20 bảng: +stock_movements, +refresh_tokens, sửa lot_allocations/fulfillments/promotions/carrier_accounts), quyết định SKIP LOCKED vs FOR UPDATE | Tuần 1 (đóng băng), áp dụng xuyên Tuần 2–5 |
| B — Trước go-live | Backup WAL + pg_dump (RPO ≤ 15 phút, RTO ≤ 4 giờ) + diễn tập restore, observability (Sentry, healthz, alert), ma trận rate limit + Turnstile, mã hóa api_token, strip EXIF, pin TZ, CI gates, k6 1.000 VU | Tuần 5–7 |
| C — Sau go-live | Tuân thủ PDPD (NĐ 13/2023), hóa đơn điện tử (NĐ 123/2020), VNPay/MoMo, đa kho, pgvector semantic search, read replica/partition | Backlog sau Tuần 8 |

**Definition of Done chung:** mọi PR qua CI gates (ruff + mypy + pytest cho backend; tsc + lint + build cho frontend); migration theo quy tắc Expand/Contract; không có lỗi Sentry mới 24h sau deploy.

---

## 1. Roadmap theo tuần

### Tuần 1 — Nền móng & đóng băng spec Nhóm A

**Mục tiêu:** stack chạy mượt trên local; mọi quyết định Nhóm A được chốt thành văn trước khi viết code nghiệp vụ.

**Tasks:**
- Pháp lý & tài khoản: mua tên miền .vn + .com; nộp đăng ký Hộ kinh doanh; mở sớm tài khoản online.gov.vn (Bộ Công Thương); đăng ký tài khoản GHN/GHTK (xin API token sandbox) và payOS/SePay (KYC); đăng ký Resend/Brevo + verify domain gửi mail (DNS SPF/DKIM).
- Dựng Monorepo: Docker Compose (Postgres 16 + pgvector, 2 Redis, FastAPI, Next.js 15) theo đúng file compose của v1.3; pin `TZ=Asia/Ho_Chi_Minh` cho toàn bộ container.
- **Chốt spec Nhóm A (review với team, merge vào tài liệu trước khi code):** luồng JWT access/refresh + rotation + revoke chuỗi; CSRF double-submit; pattern commit → enqueue ARQ → gọi provider idempotent (mục 4.4); quyết định giữ `FOR UPDATE SKIP LOCKED` + retry 409 (mặc định) hay `FOR UPDATE` thuần.
- Migration Alembic tạo **20 bảng** theo schema v1.3 (gồm `stock_movements`, `refresh_tokens`, `lot_allocations` có `uq_lot_allocation`, `fulfillments` có `attempt_no`, `promotions` có `chk_promo_used_within_limit`, `carrier_accounts` dùng cột mã hóa BYTEA).
- Code API CRUD Sản phẩm/Danh mục + pipeline tự động sinh `api-schema.d.ts` từ OpenAPI sang Next.js.
- Viết dependency `get_db` chuẩn (commit/rollback xuyên suốt request) — dùng chung cho mọi module sau này.
- Sinh `SECRET_ENCRYPTION_KEY` (AES-256-GCM) + helper mã hóa/giải mã bí mật; lưu key trong `.env` (không commit).

**Deliverables:** repo chạy `docker compose up` một lệnh; migration head = 20 bảng; sửa giá ở FastAPI tự động `revalidateTag` làm mới Next.js; tài liệu spec Nhóm A được duyệt.

**Tiêu chí nghiệm thu:**
1. `docker compose up` dựng toàn stack < 5 phút, healthcheck Postgres pass.
2. `alembic upgrade head` tạo đúng 20 bảng + đủ index; `alembic downgrade` sạch.
3. Đổi giá 1 SKU trong DB → trang sản phẩm Next.js cập nhật trong < 60s qua ARQ revalidate.
4. Không còn quyết định Nhóm A nào ở trạng thái "tbd".

### Tuần 2 — Storefront + Giỏ hàng + Auth khách hàng

**Mục tiêu:** khách xem, lọc, thêm giỏ (kể cả chưa đăng nhập) và đăng nhập gộp giỏ đúng luật.

**Tasks:**
- Dựng Storefront: Trang chủ, trang Danh mục + bộ lọc, trang Chi tiết SP (biến thể + hạn dùng gần nhất + tồn đệm fetch ≤ 30s).
- Module Giỏ hàng (`carts`, `cart_items`) + SQL gộp giỏ `ON CONFLICT DO UPDATE` khi đăng nhập.
- **Auth khách hàng theo spec v1.3 (mục 4.5):** đăng nhập Email/SĐT + Google; JWT access 15 phút / refresh 30 ngày trong cookie httpOnly + Secure + SameSite=Lax; rotation + revoke qua bảng `refresh_tokens`; `guest_token` = `secrets.token_urlsafe(32)` TTL 30 ngày; middleware CSRF (double-submit) cho mọi mutation.
- Rate limit nền: login 5 lần/phút (IP+tài khoản), áp dụng middleware chung từ đầu.

**Deliverables:** luồng guest → login gộp giỏ end-to-end; token rotation hoạt động (refresh cũ bị vô hiệu ngay).

**Tiêu chí nghiệm thu:**
1. Thêm giỏ khi chưa login → đăng nhập → số lượng cộng dồn đúng; hàng hết hiển thị nhãn, không tự xóa.
2. Dùng lại refresh token đã rotated → toàn bộ chuỗi token của user bị revoke (test bằng script).
3. Mutation không kèm `X-CSRF-Token` → 403.
4. Sai password 6 lần liên tiếp → bị rate limit (429).

### Tuần 3 — Checkout, State Machine & Tra cứu đơn

**Mục tiêu:** đặt hàng guest checkout an toàn tương tranh; tra cứu đơn chống enumeration.

**Tasks:**
- Guest Checkout + State Machine đơn hàng (conditional UPDATE, cấm read-then-write) + `order_status_history` trong cùng transaction.
- Áp dụng **pattern mục 4.4**: tạo đơn commit xong mới enqueue email; helper `enqueue_after_commit` dùng chung.
- Idempotency checkout: `orders.idempotency_key` — bấm đúp/retry trả về đúng đơn cũ.
- Trang tra cứu: mã đơn ngẫu nhiên 10 ký tự + SĐT, che thông tin, rate limit 10 lần/phút theo IP+SĐT.
- ARQ Worker gửi email xác nhận (Resend/Brevo) + cron dọn giỏ guest > 60 ngày.

**Deliverables:** checkout COD end-to-end trên local; email xác nhận tới hộp thư thật.

**Tiêu chí nghiệm thu:**
1. Test 2 request cùng xác nhận/hủy 1 đơn: chỉ 1 request thành công, không ghi đè (409 cho request thua).
2. Retry checkout cùng `idempotency_key` 3 lần → chỉ 1 đơn, 1 bộ giữ chỗ kho.
3. Tra cứu mã đơn sai 11 lần/phút → 429; kết quả đúng luôn che 3 số giữa SĐT.
4. Tắt Redis queue ngay sau commit đơn → cron re-enqueue gửi email trong ≤ 2 phút khi queue sống lại.

### Tuần 4 — Thanh toán VietQR & Vận chuyển (theo đúng ranh giới transaction v1.3)

**Mục tiêu:** tích hợp 1 cổng thanh toán + 1 hãng vận chuyển theo pattern commit → enqueue → idempotent.

**Tasks:**
- `ShippingProvider` (GHN hoặc GHTK): quote phí ship (cache Redis 15 phút), tạo vận đơn qua ARQ job (idempotent theo `fulfillments.tracking_code` + `attempt_no`), webhook cập nhật trạng thái.
- `PaymentProvider` VietQR (payOS/SePay): tạo QR (ARQ job sau commit, idempotent theo `payments.external_transaction_id`), webhook xử lý trong cùng transaction với INSERT `webhook_events`, bắt underpaid/overpaid (dung sai ≤ 1.000đ).
- Verify HMAC + timestamp webhook (chống replay, dung sai 5 phút).
- Tạo lại vận đơn cùng hãng sau hủy/giao thất bại: `attempt_no + 1` (kiểm chứng ràng buộc UNIQUE mới).
- `payments.sync_status`: cron đối chiếu đơn VietQR pending quá 10 phút.

**Deliverables:** đặt đơn → QR động → chuyển khoản thật (sandbox) → webhook ghi nhận đúng; tạo được vận đơn thật trên sandbox hãng.

**Tiêu chí nghiệm thu:**
1. Bắn webhook thanh toán lặp 3 lần → ghi nhận đúng 1 lần (`webhook_events` chặn trùng).
2. Chuyển thiếu 5.000đ → đơn chuyển `underpaid`; chuyển thừa → `overpaid`.
3. Kill worker giữa lúc gọi tạo vận đơn → retry không tạo trùng vận đơn (idempotency phía provider + check `tracking_code`).
4. Webhook giả chữ ký hoặc timestamp cũ → 401/400, không đổi trạng thái đơn.

### Tuần 5 — Kho FEFO idempotent, Sổ cái kho & Admin (kèm bảo mật staff)

**Mục tiêu:** chốt toàn bộ logic kho + trang admin vận hành được, staff đăng nhập an toàn. *(Tuần nặng nhất — xem rủi ro R1.)*

**Tasks:**
- Hoàn thiện `allocate_inventory_fefo` bản idempotent (INSERT `ON CONFLICT (order_item_id, lot_id) DO NOTHING` trước, chỉ tăng `qty_reserved` khi insert thành công).
- Bảng `stock_movements`: ghi sổ tại mọi điểm chạm tồn kho (packed, release, nhập lô, hàng hoàn, điều chỉnh tay); màn admin điều chỉnh kho **bắt buộc** chọn reason + ghi sổ.
- Cronjob: quét đơn quá hạn 15 phút (2 phút/lần, release kho + release lượt mã giảm giá), cảnh báo lô ≤ 60 ngày (0h), khóa lô hết hạn, **đối chiếu `cached_available_qty` (2h sáng)**.
- Khuyến mãi theo mục 4.6: conditional UPDATE `used_count`, vòng đời `promotion_usages` (reserved → consumed/released), test burst cùng 1 mã.
- Admin Dashboard `/admin`: Quản lý Lô, Duyệt đơn, Sửa cân nặng/số kiện, In phiếu giao, Mã giảm giá, Duyệt đánh giá (Cache-Control: no-store).
- **Auth staff:** 2FA TOTP bắt buộc cho owner/warehouse_staff/cskh_staff (+ 10 backup code); `totp_secret` mã hóa; `carrier_accounts.api_token` ghi qua lớp mã hóa envelope; strip EXIF ảnh review trong worker.

**Deliverables:** nhân viên kho xử lý đơn từ confirmed → packed → shipped trên admin; sổ cái kho truy vết được từng biến động.

**Tiêu chí nghiệm thu:**
1. Test 200 luồng mua đồng thời 1 biến thể còn 5 gói ở 2 lô: đúng 5 đơn, tách lô FEFO, kho không âm; **retry checkout không tạo allocation trùng**.
2. 200 request cùng áp 1 mã còn 10 lượt → đúng 10 đơn dùng mã; hủy 3 đơn → `used_count` giảm 3, `promotion_usages` chuyển `released`.
3. Sổ `stock_movements` đối chiếu khớp `qty_on_hand` từng lô (job 2h chạy tay, drift = 0 sau khi sửa).
4. Staff chưa enroll TOTP không vào được `/admin`; `api_token` trong DB là BYTEA, không đọc được plaintext.
5. Ảnh review sau xử lý không còn EXIF (kiểm bằng exiftool).

### Tuần 6 — Hạ tầng, CI/CD, Backup & Observability (Nhóm B)

**Mục tiêu:** production sẵn sàng vận hành: deploy tự động, backup/restore đo được, nhìn thấy hệ thống.

**Tasks:**
- Thuê VPS (4vCPU/8GB), trỏ Cloudflare (WAF, Turnstile tại login + checkout), DNS, TLS.
- GitHub Actions CI/CD: gates ruff + mypy + pytest + alembic check (backend), tsc + lint + build (frontend); build image, deploy < 3 phút, giữ 3 image cũ rollback.
- **Backup 2 lớp:** WAL archiving liên tục lên R2 (**RPO ≤ 15 phút**) + `pg_dump` hằng đêm mã hóa GPG (giữ 30 bản); viết runbook restore; **diễn tập khôi phục thật** lên VPS phụ hoặc local (**RTO ≤ 4 giờ**).
- Observability: Sentry (FE + BE + worker), endpoint `/healthz` `/readyz`, structured JSON log, alert: queue depth ARQ, đơn kẹt `pending` > 30 phút, payment `underpaid/overpaid`, cron đối chiếu phát hiện drift, Redis queue gần đầy (noeviction), uptime check bên ngoài.
- Ma trận rate limit đầy đủ trên Nginx/app theo mục 4.5.
- Trang chính sách + hồ sơ Bộ Công Thương.

**Deliverables:** push `main` → deploy tự động; dashboard Sentry có alert rule; file restore test-pass.

**Tiêu chí nghiệm thu:**
1. Deploy từ push đến live < 3 phút; rollback về image trước < 2 phút.
2. Diễn tập restore: dựng lại DB từ pg_dump + WAL, mất dữ liệu ≤ 15 phút, tổng thời gian ≤ 4 giờ (biên bản chụp màn hình).
3. CI chặn PR fail bất kỳ gate nào (thử PR cố tình lỗi).
4. Giả lập worker chết → alert bắn trong ≤ 5 phút.

### Tuần 7 — Kiểm thử tải & UAT

**Mục tiêu:** chứng minh 1.000 người dùng đồng thời; vá mọi lỗi trước mở bán.

**Tasks:**
- k6 từ máy ngoài vào staging: kịch bản browse (ISR cache) + search + checkout hỗn hợp, 1.000 VU.
- Kiểm thử bảo mật theo checklist v1.3: 2FA, CSRF, rate limit từng endpoint, webhook replay, enumeration mã đơn, quyền từng role (warehouse_staff không sửa được mã giảm giá…).
- UAT: 5–10 người quen đặt toàn trình (COD + VietQR), gồm cả hủy đơn và tạo lại vận đơn.
- Fix bug, tinh chỉnh `shared_buffers`/pool size theo kết quả đo (đảm bảo workers × pool_size + cron ≤ `max_connections=120`).

**Deliverables:** báo cáo k6; danh sách bug đã đóng; sign-off UAT.

**Tiêu chí nghiệm thu:**
1. p95 < 500ms, lỗi < 1%, RAM toàn máy ~5.5GB/8GB ở 1.000 VU.
2. Không còn bug P0/P1 mở.
3. Checklist bảo mật 100% mục pass.

### Tuần 8 — Go-live

**Mục tiêu:** mở bán thật, vận hành ổn định.

**Tasks:**
- Nhập dữ liệu sản phẩm + lô hạn dùng thật (import CSV có kiểm chứng `stock_movements` reason `lot_import`).
- Gắn logo Bộ Công Thương, bật monitoring sát (Sentry, queue, alert drift).
- Quy trình vận hành ngày: đối soát COD, xem báo cáo drift 2h, kiểm tra alert.

**Deliverables:** website live; runbook vận hành ngày/tuần.

**Tiêu chí nghiệm thu:** hệ thống vận hành thực tế ổn định 7 ngày đầu, không P0.

---

## 2. Rủi ro & phụ thuộc

### 2.1. Phụ thuộc bên ngoài (cần xin từ Tuần 1)

| Phụ thuộc | Ảnh hưởng nếu chậm | Hành động |
|---|---|---|
| API token GHN/GHTK (đăng ký shop + ký hợp đồng) | Trễ Tuần 4 | Đăng ký ngay Tuần 1; chuẩn bị fallback hãng còn lại nhờ abstraction `ShippingProvider` |
| KYC payOS/SePay | Trễ VietQR Tuần 4 | KYC Tuần 1; nếu chậm, go-live với COD trước, bật VietQR sau |
| Verify domain email (DNS) | Email rơi spam | Cấu hình SPF/DKIM/DMARC Tuần 1 |
| Hộ kinh doanh + Bộ Công Thương | Pháp lý go-live | Nộp Tuần 1, hoàn thiện hồ sơ Tuần 6 (đã có trong plan) |
| `SECRET_ENCRYPTION_KEY` | Lộ api_token nếu quản lý ẩu | Sinh Tuần 1, lưu `.env` ngoài git, backup key kèm GPG |

### 2.2. Rủi ro kỹ thuật & giảm thiểu

| # | Rủi ro | Mức | Giảm thiểu |
|---|---|---|---|
| R1 | Tuần 5 quá tải (FEFO idempotent + stock_movements + admin 5 màn + 2FA) | Cao | Ước lượng "3–4 ngày dựng admin" là lạc quan → chuyển **Duyệt đánh giá** và **Báo cáo** sang Tuần 6 nếu cần; bảo vệ tiêu chí nghiệm thu kho (mục 1–3) làm P0 |
| R2 | Sandbox payOS/GHN khác production (webhook payload, timing) | Trung | Test bằng tài khoản thật giao dịch nhỏ trong Tuần 7 (UAT), không tin sandbox tuyệt đối |
| R3 | Single VPS = SPOF (DB + queue + app) | Trung | WAL archiving RPO ≤ 15 phút + runbook restore RTO ≤ 4 giờ (Tuần 6); roadmap replica ở Nhóm C |
| R4 | k6 phát hiện bottleneck muộn (pool DB, worker ARQ) | Trung | Load test sớm dạng smoke ngay Tuần 5 với 200 VU; Tuần 7 đầy đủ 1.000 VU |
| R5 | Scope creep: thêm VNPay/MoMo/đa kho giữa chừng | Trung | Đóng băng phạm vi v1.3; mọi thứ ngoài COD+VietQR, 1 hãng vận chuyển đưa vào backlog Nhóm C |
| R6 | Nhập lô thật sai hạn dùng → FEFO xuất sai | Trung | Form nhập lô bắt buộc 2 người kiểm; import CSV có dry-run đối chiếu |
| R7 | Redis queue (noeviction) đầy khi backlog job | Thấp | Alert queue depth (Tuần 6); job email/revalidate cho phép drop có giám sát |
| R8 | Cron im lặng (worker chết) → giữ chỗ không được nhả | Trung | Alert "đơn pending > 30 phút" + heartbeat cron (Tuần 6) |

---

## 3. Backlog sau go-live (Nhóm C)

1. **Tuân thủ:** rà soát PDPD (Nghị định 13/2023/NĐ-CP) — mục đích thu thập, retention, quyền xóa dữ liệu cá nhân; đánh giá nghĩa vụ hóa đơn điện tử (Nghị định 123/2020/NĐ-CP) và chọn nhà cung cấp tích hợp.
2. **Thanh toán mở rộng:** VNPay/MoMo/ZaloPay qua `PaymentProvider` hiện có; hoàn tiền (refund) end-to-end.
3. **Vận chuyển mở rộng:** hãng thứ 2 (Viettel Post) + bảng mapping địa chính Tỉnh/Huyện/Xã theo từng hãng (hiện địa chỉ gắn ID một hãng).
4. **Scale DB theo roadmap mục 6 (v1.3):** đa kho (`warehouses` + `warehouse_id`), pgvector semantic search/chatbot, Read Replica + partition `orders`/`order_status_history`/`webhook_events` khi > 5.000 CCU.
5. **Trải nghiệm:** chương trình khách hàng thân thiết, tự động SMS/ZNS bên cạnh email.

## 4. Milestone & điểm kiểm (go/no-go)

| Cửa ải | Thời điểm | Điều kiện qua |
|---|---|---|
| M1 — Spec đóng băng | Cuối Tuần 1 | Toàn bộ Nhóm A chốt; migration 20 bảng pass |
| M2 — Mua được hàng | Cuối Tuần 3 | Checkout COD + idempotency + state machine pass test đồng thời |
| M3 — Tiền & vận đơn thật | Cuối Tuần 4 | Webhook idempotent; tạo/hủy/tạo lại vận đơn pass |
| M4 — Kho & admin | Cuối Tuần 5 | 3 tiêu chí nghiệm thu kho đầu tiên pass; 2FA staff hoạt động |
| M5 — Sẵn sàng vận hành | Cuối Tuần 6 | Restore drill đạt RPO/RTO; alert hoạt động; CI gates bắt buộc |
| M6 — Go/No-go | Cuối Tuần 7 | k6 đạt SLO; checklist bảo mật 100%; 0 bug P0/P1 |
