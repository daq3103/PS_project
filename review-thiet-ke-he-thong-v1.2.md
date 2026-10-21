---
cursor:
  subagentId: "bc-4d851842-3410-508a-aaeb-781c55bee7f7"
---

# Review tài liệu: Thiết kế hệ thống v1.2 — FastAPI & Next.js (Pet shop e-commerce)

Đối tượng review: `internal/thiet-ke-he-thong-v1.2.docx` (8 chương: tổng quan, chức năng, kiến trúc, frontend, backend, CSDL 18 bảng, scale roadmap, docker-compose, lộ trình 8 tuần).

Đánh giá chung: tài liệu **chất lượng cao so với quy mô 1 shop tự vận hành** — các quyết định khó (idempotency, chống oversell, tách 2 Redis, snapshot giá vốn) đều được nhận diện đúng. Các vấn đề còn lại chủ yếu nằm ở **bảo mật phiên đăng nhập, tính kiểm toán của kho, ranh giới transaction với dịch vụ ngoài, và độ tin cậy vận hành 1 VPS**.

---

## 1. Điểm mạnh

### 1.1. Kiến trúc FastAPI + Next.js rõ ràng, đúng quy mô
- **Modular monolith theo domain** (`catalog`, `inventory`, `cart`, `order`, `promotion`, `customer`, `payment`, `shipping`) — lựa chọn đúng: tránh microservices sớm, nhưng vẫn tách biệt nghiệp vụ đủ tốt để sau này tách service nếu cần.
- Luồng request rõ ràng: Cloudflare (CDN/WAF/Turnstile) → Nginx → Next.js (SSR/ISR, port 3000) → FastAPI (4 Uvicorn workers, port 8000) → PostgreSQL/Redis. Next.js gọi FastAPI nội bộ qua `INTERNAL_API_URL` + keep-alive — đúng chuẩn BFF-lite, không lộ API ra ngoài nếu không cần.
- Cơ chế **ISR revalidation chủ động** (FastAPI đẩy job ARQ → POST `/api/revalidate` kèm secret → `revalidateTag`) giải quyết đúng bài toán "đổi giá/tồn kho phải phản ánh ngay" mà không hy sinh cache tĩnh; bảng mapping sự kiện → hành động ở mục 3.1 rất cụ thể. Khung HTML cache 5–10 phút + hộp biến thể fetch nhẹ ≤ 30s là thiết kế hybrid hợp lý.
- **Abstraction `PaymentProvider` / `ShippingProvider` (ABC)** với method đúng trọng tâm (`verify_webhook`, `sync_status`, `map_carrier_status`) — cho phép thay GHN↔GHTK, payOS↔SePay mà không đụng code nghiệp vụ.

### 1.2. Xử lý đúng các bài toán khó nhất của e-commerce
- **Idempotency xuyên suốt**: `orders.idempotency_key` UNIQUE, `payments.idempotency_key` UNIQUE, bảng `webhook_events` với UNIQUE(provider, external_event_id) chống xử lý webhook lặp. Nguyên tắc "không tin giá/ship từ trình duyệt, tính lại từ DB ở checkout" được nêu thành văn.
- **State machine đơn hàng an toàn tương tranh**: chuyển trạng thái bằng conditional UPDATE (CAS theo trạng thái cũ, kiểm `rowcount == 0` → 409), cấm read-then-write, ghi `order_status_history` trong cùng transaction. Đây là pattern đúng chuẩn.
- **Thuật toán FEFO đa lô** (mục 4.2): sort theo `variant_id` chống deadlock, UPDATE có điều kiện `(qty_on_hand - qty_reserved) >= take_qty` chống âm kho, phân bổ nhiều lô, snapshot `unit_cost` tại thời điểm allocate → tính lợi nhuận gộp chính xác. Vòng đời `qty_reserved` (pending → confirmed → packed → cancelled) được chuẩn hóa rõ, tránh lỗi trừ kho 2 lần. Kịch bản test "200 luồng mua 5 món cuối nằm ở 2 lô" là acceptance test tốt.
- **Tách 2 Redis**: `redis-cache` (allkeys-lru, không persistence) vs `redis-queue` (noeviction + AOF everysec) — tránh đúng lỗi kinh điển "cache eviction giết queue".

### 1.3. Data model chặt chẽ
- Tiền dùng **BIGINT (VNĐ)**, PK dùng UUID, đầy đủ CHECK (`qty_on_hand >= qty_reserved`, giá/số lượng ≥ 0, `weight_grams > 0`).
- **Snapshot đầy đủ**: tên/SKU/cân nặng/đơn giá trên `order_items`, `unit_cost` trên `lot_allocations`, `coupon_code_snapshot` — báo cáo lịch sử không bị sai khi đổi dữ liệu gốc.
- **Partial index đúng tầng truy vấn**: FEFO lookup `(variant_id, expiry_date NULLS LAST) WHERE status='active' AND qty_on_hand > qty_reserved`, quét đơn hết hạn giữ chỗ, đối soát COD chưa về, GIN cho `attributes` JSONB.
- `order_status_history` có `actor_type` (customer/staff/system_cron/webhook) — truy vết tốt.

### 1.4. Bảo mật & vận hành có chiều sâu (ở những phần đã nêu)
- Tra cứu đơn: mã đơn ngẫu nhiên 10 ký tự (không ID tự tăng), che SĐT/địa chỉ, rate limit theo IP+SĐT — chống enumeration đúng cách.
- Upload ảnh review qua **presigned URL R2**, giới hạn jpg/png/webp ≤ 5MB, duyệt trước khi hiển thị.
- Argon2 cho password, HMAC verify webhook (trong `security.py`), RBAC 3 vai trò + owner.
- Docker Compose có `mem_limit` từng service kèm lý do (Next.js OOM), log rotation, healthcheck Postgres, backup pg_dump + mã hóa GPG lên R2 + **diễn tập restore**, k6 load test với SLO cụ thể (p95 < 500ms, lỗi < 1%). Lộ trình 8 tuần có tiêu chí nghiệm thu từng tuần — thực tế, kể cả việc xếp pháp lý (Hộ KD, Bộ Công Thương) vào tuần 1.

---

## 2. Điểm yếu / Rủi ro

### 2.1. Bảo mật — khoảng trống lớn nhất nằm ở phiên đăng nhập & admin
1. **Chiến lược token chưa được định nghĩa**: tài liệu nêu "JWT, Argon2" nhưng không nói access/refresh lifetime, lưu ở đâu (httpOnly cookie hay localStorage — rủi ro XSS), rotation, revocation. Với hệ có vai trò staff, đây là quyết định bắt buộc phải chốt trước khi code.
2. **Không nhắc CSRF** dù admin dùng chung domain Next.js (nếu chọn cookie auth thì bắt buộc phải có).
3. **Admin `/admin` chỉ bảo vệ bằng Role Guard ở tầng app**: chưa có 2FA cho owner/staff, chưa có IP allowlist/basic-auth ở Nginx cho nhánh admin. Tài khoản owner điều khiển tiền, kho, mã giảm giá mà chỉ có 1 lớp password là yếu.
4. **`guest_token` chưa spec độ entropy/thời hạn** — token yếu = trộm giỏ hàng.
5. **Rate limit mới chỉ nêu cho endpoint tra cứu đơn**; login, checkout, gửi review, áp mã giảm giá chưa có ma trận giới hạn. Turnstile mới gắn ở mức "bật trên Cloudflare", chưa gắn vào form cụ thể (checkout, login).
6. **`carrier_accounts.api_token` lưu plaintext trong DB** — token GHN/GHTK lộ khi lộ DB. Cần mã hóa at-rest (app-level envelope hoặc pgcrypto).
7. Ảnh review: validate mime/size nhưng **chưa nói re-encode/strip EXIF** (ảnh chụp điện thoại lộ GPS).
8. **Tuân thủ VN**: có đăng ký Bộ Công Thương, nhưng chưa nhắc **Nghị định 13/2023 (PDPD)** về dữ liệu cá nhân (SĐT/địa chỉ khách, retention, quyền chủ thể dữ liệu) và **hóa đơn điện tử (Nghị định 123/2020)** — nghĩa vụ thực tế khi bán online.

### 2.2. Kho & tính toàn vẹn dữ liệu — thiếu sổ cái và đường đối chiếu
1. **Không có bảng stock ledger (sổ cái kho)**: mọi thay đổi `qty_on_hand` ngoài đơn hàng (kiểm kê, hư hỏng, điều chỉnh tay, nhập sai) không có audit trail. `lot_allocations` + `returned_stock` chỉ bao phủ luồng đơn. Với hệ đề cao tính đúng của kho, đây là thiếu sót đáng kể.
2. **`cached_available_qty` chỉ thấy thao tác trừ** (khi allocate) — đường cộng lại khi hủy/hết hạn giữ chỗ không được mô tả; không có job đối chiếu `cached_available_qty = SUM(qty_on_hand - qty_reserved)` → rủi ro drift âm thầm làm web hiển thị sai tồn.
3. **`FOR UPDATE SKIP LOCKED` vs tính FEFO tuyệt đối**: khi 2 giao dịch tranh nhau, giao dịch sau sẽ *bỏ qua* lô bị khóa (thường là lô hạn gần nhất) và allocate từ lô hạn xa hơn → vi phạm FEFO dưới tải đồng thời; đồng thời có thể báo "không đủ tồn kho" giả dù hàng còn (do skip). Cần viết rõ trade-off hoặc dùng plain `FOR UPDATE` (đã sort chống deadlock rồi).
4. **Idempotency của chính hàm allocate**: `lot_allocations` không có ràng buộc UNIQUE(order_item_id, lot_id) — nếu checkout retry sau lỗi giữa chừng, có nguy cơ ghi allocation trùng. Cần UNIQUE + upsert hoặc short-circuit bằng `idempotency_key` trước khi allocate (tài liệu chưa chỉ rõ orchestration này).
5. **Promotion race**: `promotions.used_count` tăng thế nào dưới burst đồng thời chưa được spec (cần conditional UPDATE `used_count < usage_limit` trong transaction) — kịch bản 200 người cùng dùng 1 mã còn 10 lượt sẽ over-redeem. Cũng chưa nêu **giải phóng lượt dùng khi đơn hủy** → mã bị "cháy" oan.
6. **`fulfillments` UNIQUE(order_id, carrier_code)**: chặn luôn khả năng tạo lại vận đơn cùng hãng sau khi hủy/giao thất bại — thực tế vận hành rất hay gặp. Cần thêm `attempt_no` hoặc bỏ ràng buộc này (giữ UNIQUE trên `tracking_code`).
7. **Địa chỉ gắn cứng ID của một hãng vận chuyển** (`province_id/district_id/ward_code` của GHN *hoặc* GHTK): khi thêm hãng thứ 2 (tài liệu có dự kiến Viettel Post) sẽ cần bảng mapping master-data — hiện chưa có.
8. **Thiếu audit log thao tác admin** (đổi giá, tạo mã giảm giá, điều chỉnh lô) — chỉ có `order_status_history`. Shop có nhiều nhân viên cần biết "ai đổi giá SKU này lúc nào".

### 2.3. Kiến trúc & tích hợp — ranh giới transaction chưa rõ
1. **Không quy định ranh giới DB transaction khi gọi dịch vụ ngoài**: `create_payment` (tạo QR) hay `create_shipment` là network call — nếu đặt trong transaction DB sẽ kẹt connection/lock; nếu đặt sau commit mà không có outbox thì mất job khi worker chết. Cần ghi rõ pattern: *commit DB trước → enqueue ARQ (at-least-once) → gọi provider idempotent*, hoặc transactional outbox.
2. **Session lifecycle chưa nêu**: `HTTPException` raise giữa `allocate_inventory_fefo` — chỉ an toàn nếu dependency FastAPI rollback session trên exception; tài liệu không ghi pattern này. Ngoài ra raise HTTPException từ tầng service là lỗi layering nhỏ (nên raise domain exception, map ở API layer).
3. **Xác thực cho admin SSR chưa rõ**: ai verify JWT khi Next.js render nhánh `/admin` — middleware Next.js hay chỉ FastAPI? Chưa mô tả luồng token từ login → FE → API.
4. **Revalidate ISR không có cơ chế đảm bảo**: nếu Next.js down đúng lúc FastAPI bắn revalidate, ARQ retry hay bỏ sót? Chưa nêu retry policy.

### 2.4. Khả năng mở rộng & độ tin cậy vận hành
1. **Single VPS = SPOF cho mọi thứ** (DB, queue, app). Chấp nhận được ở giai đoạn đầu nhưng tài liệu **không ghi RTO/RPO mục tiêu**. Sơ đồ kiến trúc nói "Backup pg_dump + WAL" lên R2, nhưng tuần 6 chỉ nói pg_dump đêm — **mâu thuẫn nội tại**: nếu có WAL archiving thật thì RPO ~ phút, nếu chỉ pg_dump đêm thì RPO 24h. Phải chốt một trong hai.
2. **Toán connection pool chưa có**: 4 Uvicorn workers × pool_size + worker + cron + migration vs `max_connections=120` — cần ghi pool_size cụ thể (ví dụ 10–15/worker) để không vỡ khi scale workers.
3. **Cron nằm trong 1 worker container duy nhất**: worker chết → đơn quá hạn 15 phút không được nhả giữ chỗ, lô hết hạn không bị khóa. `restart: always` giảm thiểu nhưng cần alert khi job im lặng (không có cơ chế nêu trong tài liệu).
4. **Observability mỏng**: mới có Sentry (tuần 8) — chưa có structured log, health/readiness endpoint, metric queue depth, alert khi `underpaid/overpaid` tăng, khi đơn kẹt `pending` bất thường (reservation leak), khi Redis queue đầy (noeviction → push fail).
5. **Mốc "3–4 ngày dựng 5 màn hình admin" là lạc quan**: màn FEFO nhập lô, xử lý đơn + sửa cân/số kiện + in tem không phải CRUD thường; tuần 5 dồn cả FEFO backend + admin → rủi ro trượt lịch cao nhất trong plan.
6. Chưa pin **timezone** (`TZ=Asia/Ho_Chi_Minh`) cho container — FEFO dùng `CURRENT_DATE`, cron "0h đêm" phụ thuộc TZ container.
7. Giỏ guest **không có TTL dọn dẹp** → `carts/cart_items` phình theo thời gian.
8. CI/CD tuần 6 chỉ nói deploy < 3 phút; **chưa có gate chất lượng** (ruff/mypy, tsc, pytest, build) trong pipeline.

---

## 3. Đề xuất cải thiện (theo thứ tự ưu tiên)

**Nhóm A — phải chốt trước khi code (tuần 1–2):**
1. Viết mục "Authentication & Session": JWT access ngắn hạn + refresh rotation, lưu httpOnly Secure cookie (SameSite=Lax) + CSRF token cho mutation, cách revoke; 2FA (TOTP) bắt buộc cho owner/staff; cân nhắc IP allowlist `/admin` ở Nginx.
2. Chốt ranh giới transaction với dịch vụ ngoài: commit DB → enqueue ARQ → gọi provider idempotent; thêm bảng outbox hoặc quy ước "job phải tự idempotent + retry". Ghi rõ session rollback-on-exception ở dependency FastAPI.
3. Bổ sung bảng **stock_movements** (ledger: lot_id, delta, reason enum [order_deduct, return, adjustment, damage, stocktake], ref_id, actor) và job đối chiếu đêm `cached_available_qty`.
4. Sửa schema: thêm UNIQUE(order_item_id, lot_id) cho `lot_allocations` (+ upsert); đổi UNIQUE `fulfillments` thành (order_id, carrier_code, attempt_no); thêm `attempt_no`; thêm bảng mapping địa chính theo hãng vận chuyển.
5. Spec vòng đời lượt dùng mã giảm giá: reserve khi tạo đơn (conditional UPDATE `used_count < usage_limit`), release khi hủy, hoàn tất khi delivered.
6. Quyết định `SKIP LOCKED` vs `FOR UPDATE` trong FEFO và ghi trade-off; nếu giữ SKIP LOCKED, thêm hướng xử lý 409 "tồn kho giả" (retry 1 lần sau backoff).

**Nhóm B — trước go-live (tuần 5–7):**
7. Chốt backup: bật WAL archiving liên tục lên R2 (RPO ≤ 5–15 phút) + pg_dump đêm, viết runbook restore, ghi RTO mục tiêu; gỡ mâu thuẫn giữa sơ đồ và tuần 6.
8. Observability tối thiểu: structured JSON log, `/healthz`/`/readyz`, alert queue depth / đơn kẹt pending / payment underpaid-overpaid / lô bị lock bất thường; uptime check ngoài (Better Stack/UptimeRobot).
9. Ma trận rate limit (login, checkout, review, promo, tracking) + gắn Turnstile vào checkout & login; spec `guest_token` (≥128-bit random, TTL) + cron dọn giỏ guest cũ.
10. Mã hóa `carrier_accounts.api_token` at-rest; re-encode + strip EXIF ảnh review; bổ sung bảng audit log thao tác admin.
11. Pin `TZ=Asia/Ho_Chi_Minh` trong toàn bộ container; ghi rõ DB pool sizing (workers × pool_size, chừa headroom cho cron/migration).
12. CI gate: ruff + mypy + pytest (backend), tsc + lint + build (frontend), alembic check; giữ chính sách migration Expand/Contract trong CI.

**Nhóm C — sau go-live / roadmap:**
13. Tuân thủ: soạn mục PDPD (NĐ 13/2023) — mục đích thu thập, retention, quyền xóa dữ liệu; lên kế hoạch tích hợp hóa đơn điện tử (NĐ 123/2020) nếu doanh thu yêu cầu.
14. Dời bớt khối lượng tuần 5 (đưa review moderation hoặc báo cáo sang tuần 6) để giảm rủi ro trượt lịch.
15. Khi thêm hãng vận chuyển thứ 2: tận dụng bảng mapping địa chính (mục 4) thay vì sửa `customer_addresses`.

---

## 4. Kết luận nhanh

| Khía cạnh | Đánh giá |
|---|---|
| Kiến trúc FastAPI + Next.js | Tốt: modular monolith rõ domain, ISR revalidation chủ động, abstraction payment/shipping đúng |
| Tech stack | Chuẩn, hiện đại, phù hợp quy mô (FastAPI/SQLAlchemy 2.0 async, Next.js 15, PG16, Redis 7.4, ARQ) |
| Data model | Chặt (BIGINT tiền, CHECK, partial index, snapshot) nhưng thiếu stock ledger, audit admin, và 2–3 ràng buộc cần sửa |
| Bảo mật | Tốt ở enumeration/upload/RBAC; **hở ở session/JWT, 2FA admin, CSRF, secrets at-rest** |
| Scalability | Đủ cho mục tiêu 1.000 CCU có k6 kiểm chứng; SPOF 1 VPS chấp nhận được nhưng phải chốt RPO/RTO và alert |
| Rủi ro lớn nhất | (1) transaction boundary với payment/shipping provider, (2) drift tồn kho do thiếu ledger + đối chiếu, (3) bảo mật phiên admin, (4) mâu thuẫn backup WAL vs pg_dump |
