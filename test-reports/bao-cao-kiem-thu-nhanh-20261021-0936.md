# Báo cáo kiểm thử nhanh — PS_project

- Thời gian: 2026-10-21 09:36 (Asia/Saigon)
- So với: ao-cao-kiem-thu-lai-20261021-0919.md (lần Redis auth gãy login)
- Phạm vi hẹp: login, worker, COD, track, BUG-02/03/04/08, owner reads
- Mật khẩu owner không ghi vào báo cáo
- JSON: quick-retest-results.json

## Kết quả từng hạng mục

| Hạng mục | Status | Bằng chứng rút gọn |
|----------|--------|-------------------|
| Login customer | PASS | 200 cookies=['access_token', 'refresh_token', 'csrf_token'] {"id":"5aed05b1-1791-40e1-ab4a-20eba77c95a4","email":"qa.qui |
| Login owner | PASS | 200 role_ok=True {"id":"2b30a4ef-39eb-498e-99e6-cb2e7964c94b","email":"owner@demo.com","phone":nu |
| Worker container | PASS | Up; cron OK |
| Guest COD checkout | PASS | 201 {"id":"3221feae-1398-4fe6-a4ca-93497614a15f","order_code":"TOA8XHSTE6","status":"confirmed","payment_method":"cod"," |
| Track order | PASS | 200 {"order_code":"TOA8XHSTE6","status":"confirmed","payment_status":"unpaid","total_amount":119000,"customer_name":"QA  |
| BUG-02 VietQR self-confirm | PASS | 403 before=pending/unpaid {"detail":"Đơn VietQR cần thanh toán trước khi xác nhận"} |
| BUG-04 Cart overstock | PASS | 409 over=89 stock=49 {"detail":"Chỉ còn 49 sản phẩm trong kho"} |
| BUG-03 ports published | FAIL | 5432/6379/6380 still open on host |
| BUG-03 Redis requirepass | PASS | 6379_pong=False 6380_pong=False |
| BUG-08 /admin anon | FAIL | 200 len=11121 |
| Owner reads (dash/orders) | PASS | dash=PASS orders=PASS |
| Customer blocked admin | PASS | 403 {"detail":"Staff access required"} |

## Thay đổi so với lần retest trước

- **Đã hồi phục:** login customer/owner (trước 500), worker Up (trước crash loop), guest COD + track, owner reads
- **BUG-02 ĐÃ SỬA:** confirm VietQR unpaid → **403** "Đơn VietQR cần thanh toán trước khi xác nhận"
- **BUG-04 ĐÃ SỬA:** cart qty>stock → **409** "Chỉ còn 49 sản phẩm trong kho"
- **BUG-03:** Redis vẫn requirepass (PASS); cổng 5432/6379/6380 vẫn publish (FAIL)
- **BUG-08:** vẫn FAIL — /admin anon trả HTML ~11KB; API admin anon vẫn 401

## Lỗi mới

Không thấy lỗi mới nghiêm trọng trong phạm vi này. Worker log có send_order_confirmation_email → skipped_no_api_key (cấu hình email thiếu, không chặn checkout).

## Counts

| Status | n |
|--------|---|
| PASS | 16 |
| FAIL | 4 |
| BLOCKED | 0 |

(Worker ghi thêm PASS thủ công từ docker ps + logs)

## Verdict

**Cải thiện rõ — local demo dùng được lại.** Login/checkout/track/owner OK; BUG-02 và BUG-04 đã vá. Còn lại chủ yếu BUG-03 (cổng publish) và BUG-08 (UI admin lộ shell). **Chưa sẵn sàng public** nếu vẫn mở DB/Redis ra host và chưa chặn /admin phía FE, nhưng **sẵn sàng tiếp tục dev/demo nội bộ**.
