# Runbook vận hành (ngắn)

## Hàng ngày (15 phút)

- [ ] Kiểm tra `/healthz` và `/readyz` (API + worker).
- [ ] Sentry: lỗi mới P0/P1 trong 24h.
- [ ] Hàng đợi ARQ: depth bình thường, không backlog > 30 phút.
- [ ] Đơn `pending` / VietQR quá 15 phút: xử lý hoặc huỷ (cron release kho).
- [ ] Đối soát COD với shipper (cuối ngày).

## 2 giờ / ca kho

- [ ] Admin → Đơn hàng: xác nhận COD, đóng gói đơn đã thanh toán.
- [ ] Lô sắp hết hạn (≤ 60 ngày): ưu tiên xuất FEFO.

## Hàng tuần

- [ ] Xem báo cáo drift `cached_available_qty` (cron 2h sáng).
- [ ] Kiểm tra backup pg_dump đêm qua + dung lượng disk.
- [ ] Rà soát mã giảm giá sắp hết hạn.

## Sự cố thường gặp

| Triệu chứng | Việc làm |
|---|---|
| Checkout 409 tồn kho | Báo khách, nhập lô hoặc giảm SL |
| Worker chết | Restart `fastapi-worker`, xem log Redis |
| VietQR pending lâu | `sync_status` / webhook payOS, kiểm tra chữ ký |
| Site chậm | Cloudflare cache, pool DB, RAM VPS |

## Liên hệ

- On-call: owner + warehouse (Telegram/Zalo nội bộ).
- Rollback deploy: GitHub Actions → image trước (< 2 phút).
