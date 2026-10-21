# Checklist bảo mật — Tuần 7 (UAT)

Đánh dấu pass/fail trước go-live. Tham chiếu plan v1.3 Tuần 7.

## Auth & session

- [ ] JWT access 15 phút, refresh rotation + reuse revoke chain
- [ ] Cookie httpOnly Secure SameSite=Lax; không lưu token trong localStorage
- [ ] Staff bắt buộc 2FA TOTP; backup codes hoạt động
- [ ] Role RBAC: `warehouse_staff` không sửa promotion; `cskh_staff` không điều chỉnh kho

## CSRF & mutation

- [ ] Mọi POST/PATCH/DELETE từ browser có `X-CSRF-Token` khớp cookie
- [ ] Webhook provider bỏ qua CSRF, verify HMAC + timestamp ±5 phút

## Rate limit

- [ ] Login / register brute-force → 429
- [ ] Checkout → giới hạn hợp lý theo IP
- [ ] Tra cứu đơn: 10 lần/phút/IP+SĐT; không lộ đơn tồn tại qua timing
- [ ] Áp mã giảm giá / review → có limit

## Checkout & thanh toán

- [ ] `idempotency_key` retry → một đơn, một allocation
- [ ] Giá/ship tính lại server-side, không tin client
- [ ] Webhook VietQR replay 3 lần → ghi nhận 1 lần (`webhook_events`)
- [ ] Underpaid/overpaid trong dung sai 1.000đ

## Enumeration & privacy

- [ ] Tra cứu đơn che 3 số giữa SĐT, che địa chỉ chi tiết
- [ ] Không trả stack trace / SQL ra client

## Admin & secrets

- [ ] `/admin` Cache-Control no-store
- [ ] `carrier_accounts.api_token` mã hoá at-rest (AES-GCM)
- [ ] `.env` / encryption key không trong git
- [ ] Upload review: strip EXIF, giới hạn MIME/size

## Hạ tầng

- [ ] TLS + Cloudflare WAF; Turnstile login + checkout (staging/prod)
- [ ] Nginx rate limit / basic-auth hoặc IP allowlist nhánh admin (nếu bật)
- [ ] Backup restore đã diễn tập (RPO/RTO đạt mục tiêu)

## Ghi chú tester

Ngày test: __________  
Người ký: __________  
Kết quả: ☐ Pass ☐ Fail (đính kèm ticket)
