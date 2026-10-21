# Báo cáo kiểm thử giao diện (Playwright) — PS_project

- Thời gian: 2026-10-21 10:07 (Asia/Saigon)
- Công cụ: Playwright 1.55 + Chromium trong thư mục tách D:\code\PS_project\qa-e2e (không sửa rontend/package.json)
- Base URL: http://localhost:3000
- Viewport: desktop 1440×900, tablet 768×1024, mobile 390×844
- Bỏ qua: luồng GHN / tạo vận đơn (chưa tích hợp, theo yêu cầu)
- An toàn: chỉ tạo dữ liệu QA; ẩn (soft-delete) sản phẩm QA; không xóa dữ liệu seed; không ghi mật khẩu owner vào báo cáo
- Screenshot: 	est-reports/screenshots/ (54 file PNG)
- JSON: 	est-reports/playwright-results.json

## 1. Tổng số test

| Trạng thái | Số |
|-----------|-----|
| PASS | 31 |
| FAIL | 1 |
| SKIPPED | 13 |
| **Tổng case Playwright** | **45** |

Ghi chú skip: các flow customer/admin/ESLint chỉ chạy 1 lần trên desktop (tablet/mobile skip có chủ đích). ESLint skip vì chưa cấu hình non-interactive.

## 2. Kết quả theo hạng mục

| Hạng mục | Kết quả | Ghi chú |
|----------|---------|---------|
| Trang chính desktop/tablet/mobile | **PASS** | /, /search, /cart, /login, /register, /checkout, /track-order, /account, /admin — không 5xx / hard console |
| Console errors / failed requests (hard) | **PASS** | Không TypeError/5xx trên các trang load tĩnh (trừ flow track khi submit — xem bug) |
| Customer: browse → add cart → COD checkout | **PASS** | Đặt hàng thành công, có mã đơn |
| Customer: track order UI | **FAIL (P1)** | Sau tra cứu, trang crash Application error |
| VietQR payment status UI | **PASS** | Hiện VietQR + trạng thái unpaid/pending (và/hoặc QR) |
| Admin login owner + click-through | **PASS** | Dashboard, orders, lots, products, promotions, reviews, reports, settings |
| Admin tạo/sửa/ẩn sản phẩm QA | **PASS** | Tạo + edit + ẩn sản phẩm QA E2E Product * (không có nút xóa cứng trên UI) |
| Admin category CRUD | **NOT RUN** | Không có trang /admin/categories |
| TOTP UI | **PARTIAL / PASS UI** | Mở được Thiết lập TOTP / enroll; **không** verify để tránh khóa tài khoản demo |
| ESLint | **NOT RUN** | Không có eslint config; 
ext lint interactive |
| GHN shipping UI | **SKIP** | Theo yêu cầu |

## 3. Bug theo mức nghiêm trọng

### P1 — High

**BUG-UI-01 — /track-order crash khi hiển thị kết quả**

- Bước: COD checkout thành công → vào Tra cứu → nhập mã đơn + SĐT → Tra cứu
- Actual: Application error: a client-side exception...
- Console: Cannot read properties of undefined (reading 'street')
- Nguyên nhân khả dĩ: UI đọc order.shipping_address.street trong khi API track trả shipping_address_masked (shape khác / thiếu street)
- File liên quan: rontend/src/app/(storefront)/track-order/page.tsx
- Ảnh hưởng: khách **không xem lại được đơn** trên UI sau khi đặt hàng (API /orders/track vẫn 200)
- Bằng chứng: screenshots/flow-track.png, low-track-query.png, console PAGEERROR
- Đề xuất: map đúng field từ shipping_address_masked (hoặc optional chaining + fallback)

### P2 — Medium

**BUG-UI-02 — Deep link /track-order?order_code=&phone= cũng crash** (cùng root-cause BUG-UI-01 khi auto-lookup thành công)

### P3 — Low / nợ

- **Category admin CRUD không có UI** — chỉ chọn category có sẵn khi tạo sản phẩm
- **Xóa cứng sản phẩm không có trên UI** — chỉ Ẩn/hidden (chấp nhận được nếu đúng thiết kế)
- **ESLint chưa cấu hình** — không chạy non-interactive được
- **Admin /admin vẫn xem được shell khi chưa login** (đã ghi ở báo cáo API trước; screenshot desktop-admin / mobile-admin)

## 4. Luồng ổn

- Storefront responsive 3 viewport
- Thêm giỏ, checkout COD + VietQR (hiển thị trạng thái)
- Owner đăng nhập, điều hướng đủ menu admin
- Tạo / sửa / ẩn sản phẩm QA
- TOTP settings mở enroll UI

## 5. Chưa test / bỏ qua

| Mục | Lý do |
|-----|-------|
| GHN pack/ship/label | Chưa tích hợp — skip theo yêu cầu |
| Category create/edit/delete UI | Không có trang admin |
| Hard delete product | Không có nút trên UI |
| TOTP verify end-to-end | Cố ý không kích hoạt trên owner demo |
| ESLint | Chưa có config non-interactive |
| Firefox/WebKit | Chỉ cài Chromium |

## 6. Cách chạy lại

`at
cd D:\code\PS_project\qa-e2e
npm test
`

(Cần file .env local với OWNER_EMAIL / OWNER_PASSWORD — đã .gitignore)

## 7. Verdict

**UI storefront + admin cơ bản dùng được trên desktop/tablet/mobile**, owner quản lý sản phẩm QA OK, VietQR hiển thị trạng thái OK.  
**Chặn trải nghiệm sau checkout:** trang tra cứu đơn **crash P1** — cần vá trước khi demo cho khách.  
**Verdict: chưa sẵn sàng public** cho đến khi sửa BUG-UI-01; phù hợp tiếp tục dev nội bộ.

### Danh sách screenshot chính

- admin-dashboard.png
- admin-nav_admin.png
- admin-nav_admin_inventory-lots.png
- admin-nav_admin_orders.png
- admin-nav_admin_products.png
- admin-nav_admin_promotions.png
- admin-nav_admin_reports.png
- admin-nav_admin_reviews.png
- admin-nav_admin_settings.png
- admin-product-create-error.png
- admin-product-create-filled.png
- admin-product-created.png
- admin-product-edit-drawer.png
- admin-product-edited.png
- admin-product-hidden.png
- admin-products-before.png
- admin-settings-totp.png
- admin-totp-enroll.png
- desktop-account.png
- desktop-admin.png
- desktop-cart.png
- desktop-checkout.png
- desktop-home.png
- desktop-login.png
- desktop-register.png
- desktop-search.png
- desktop-track-order.png
- flow-added-cart.png
- flow-cart.png
- flow-checkout-filled.png
- flow-checkout-result.png
- flow-home.png
- flow-product.png
- flow-track-query.png
- flow-track.png
- flow-vietqr-result.png
- mobile-account.png
- mobile-admin.png
- mobile-cart.png
- mobile-checkout.png
- mobile-home.png
- mobile-login.png
- mobile-register.png
- mobile-search.png
- mobile-track-order.png
- tablet-account.png
- tablet-admin.png
- tablet-cart.png
- tablet-checkout.png
- tablet-home.png
- tablet-login.png
- tablet-register.png
- tablet-search.png
- tablet-track-order.png
