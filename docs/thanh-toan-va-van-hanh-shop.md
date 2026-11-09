# Thanh toán và vận hành Shop

COD luôn có trong checkout. Khách xem báo giá cuối rồi mới xác nhận đặt. Đơn COD mới chờ nhân viên xác nhận; nếu chưa xác nhận sau 24 giờ sẽ được hủy và nhả hàng. Mẫu cũ tự xác nhận COD đã được thay bằng luồng này.

## Bật thanh toán online qua payOS

1. Tạo tài khoản tại https://my.payos.vn, xác minh cá nhân/doanh nghiệp theo yêu cầu và tạo kênh thanh toán gắn tài khoản ngân hàng.
2. Trong `.env` ở gốc project, đặt:

```dotenv
PAYMENT_PROVIDER=payos
PAYOS_CLIENT_ID=gia_tri_tu_kenh_cua_ban
PAYOS_API_KEY=gia_tri_tu_kenh_cua_ban
PAYOS_CHECKSUM_KEY=gia_tri_tu_kenh_cua_ban
APP_PUBLIC_URL=https://ten-mien-cua-ban
```

3. Cấu hình webhook của đúng kênh tới `https://ten-mien-cua-ban/api/v1/webhooks/payos`. Việc xác nhận webhook thực hiện trên kênh của bạn, không được tự đăng ký hộ khi chưa có tài khoản/khóa.
4. Tạo lại API và worker để nhận biến môi trường mới:

```powershell
docker compose -f docker-compose.yml -f docker-compose.4gb.yml up -d --no-build --no-deps --force-recreate fastapi-api fastapi-worker
```

Thiếu cấu hình hoặc địa chỉ HTTPS thì lựa chọn online được ẩn; khách vẫn chọn COD. Chỉ các khóa server ở trên được dùng; không tạo `NEXT_PUBLIC_PAYOS_*`. Không sử dụng bộ mô phỏng để nhận tiền thật.

Link thanh toán được worker tạo sau khi đơn đã lưu. Checkout đợi tối đa khoảng một phút để hiện liên kết. Có thể mở lại ở Đơn hàng của tôi. Nếu nhà cung cấp lỗi, vào Việc cần xử lý để xem và thử lại sau khi sửa cấu hình. Bản hiện tại xác nhận khoản thu qua webhook; đối soát polling định kỳ là đầu việc còn thiếu được ghi trong bảng đối chiếu.

URL quay lại từ payOS chỉ mở trang theo dõi. Không dùng tham số `success` từ trình duyệt để ghi nhận đã trả. Quyền xem đơn được kiểm tra bằng phiên hiện tại hoặc liên kết riêng gửi trong email. Token tra cứu không được đưa vào return/cancel URL gửi sang nhà cung cấp.

## Phí giao hàng

`SHIPPING_BASE_FEE` cộng `SHIPPING_PER_KG_FEE` cho mỗi kg làm tròn lên từ tổng cân nặng sản phẩm. Đây là phí shop thu của khách, hiển thị trước đặt đơn; không phải báo giá trực tiếp từ GHN. Cân nặng vận đơn phải bao gồm bao bì và được nhân viên nhập khi ghi nhận vận đơn.

Muốn tự động tạo vận đơn với GHN/GHTK/Viettel Post cần tích hợp adapter, địa chỉ theo mã hãng, token và quy trình đối soát riêng. Hiện tại hãy tạo vận đơn trong tài khoản hãng rồi nhập hãng, mã, cân nặng và số kiện tại chi tiết đơn hàng. Vận đơn mô phỏng chỉ dành cho phát triển.

## Kho và hủy đơn

- Nhập lô có hạn dùng khi sản phẩm yêu cầu. `INVENTORY_MIN_SHELF_LIFE_DAYS` là biên toàn shop; 0 vẫn loại lô hết hạn hôm nay và trước đó. Cần chọn biên phù hợp thời gian giao trước khi bán thật.
- Đóng gói giữ nguyên lượng thực có. Bấm Giao hàng lúc thực sự bàn giao mới xuất kho và tiêu thụ giữ chỗ.
- Hủy trước bàn giao nhả giữ chỗ. Đơn đã có khoản thu tạo việc cần hoàn/đối chiếu; chưa tự đánh dấu đã hoàn.
- Đơn lịch sử đã xuất kho theo cơ chế cũ lúc đóng gói phải kiểm tra thủ công trước hủy. Không cộng hàng vào kho bằng cách hủy đơn.

## Hỗ trợ và công việc chờ

Khách vào Tài khoản → Yêu cầu hỗ trợ và đổi trả. Nhân viên có quyền chăm sóc khách hàng xử lý tại Quản trị → Hỗ trợ khách hàng. Quyền kho không tự mở được yêu cầu riêng của khách. Trạng thái gồm đã tiếp nhận, đang xử lý, chờ khách phản hồi và đóng.

Quản trị → Việc cần xử lý hiển thị tác vụ chờ/lỗi và khoản tiền cần đối chiếu. Sau khi thực hiện hoàn hoặc xử lý với ngân hàng bên ngoài, chủ cửa hàng lưu chứng từ duy nhất và nội dung giải quyết. Nút này ghi nhận xử lý thủ công, không tự chuyển tiền. Chưa có quy trình hoàn một phần/đổi trả theo dòng đầy đủ.

Tác vụ được lưu trong PostgreSQL và chỉ hoàn tất sau khi hàm xử lý xong. Lease 3 phút phục hồi khi worker dừng; sau 5 lần thất bại công việc được giữ ở trạng thái cần kiểm tra. Email có khóa gửi lại để giảm trùng; không cam kết gửi đúng một lần vô thời hạn khi nhà cung cấp không hỗ trợ cơ chế đó.

## Kiểm thử an toàn

`backend/scripts/test_commerce_plan.py` tự tạo database `pethome_plan_test_*`, migrate, chạy pytest và xóa riêng database đó. Cần runtime có pytest/pytest-asyncio. Trong local dùng container hạn chế RAM; không chạy pytest trực tiếp trên database shop. Hai Redis dùng database 15 cho bộ test, không xóa database Redis của hệ thống.

Backup trước migration ở `.local-backups/pethome-before-plan-0010.dump`. Đây là dữ liệu nội bộ có thông tin tài khoản; không commit hoặc gửi công khai. Kiểm thử khôi phục đã chạy trên database thử, không thay cho backup ngoài máy/WAL của môi trường bán thật.
