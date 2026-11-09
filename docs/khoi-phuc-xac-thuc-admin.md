# Khôi phục ứng dụng xác thực của quản trị viên

Thao tác do người vận hành có quyền truy cập máy chủ thực hiện khi đã xác nhận đúng chủ tài khoản. Không lấy khóa cũ ra khỏi database để sinh mã thay cho chủ tài khoản.

Script `backend/scripts/reset_admin_totp.py` chỉ hỗ trợ tài khoản quản trị viên đang hoạt động và có mật khẩu. Mặc định chỉ xem trước trạng thái. Khi xác nhận, script xóa khóa xác thực cũ, tắt trạng thái đã liên kết, vô hiệu hóa các phiên đăng nhập cũ và thu hồi phiên làm mới. Các API ghi quản trị vẫn yêu cầu thiết lập xác thực hai bước trước khi sử dụng.

Ví dụ xem trước trên Docker hiện tại, từ thư mục project:

```powershell
Get-Content -Raw backend/scripts/reset_admin_totp.py | docker compose exec -T fastapi-api python - --email admin@petshop.example.com
```

Sau khi chủ tài khoản xác nhận, thêm `--confirm` vào cuối lệnh trên. Không chạy cho tài khoản khác khi chưa xác minh.

Chủ tài khoản thực hiện tiếp:

1. Đăng nhập lại PetHome bằng email và mật khẩu.
2. Mở **Cài đặt bảo mật** trong trang quản trị.
3. Chọn **Thiết lập xác minh hai bước**.
4. Trên ứng dụng xác thực ở điện thoại, thêm tài khoản bằng khóa thiết lập mà PetHome hiển thị. Chọn loại mã theo thời gian nếu ứng dụng yêu cầu. Khóa này là bí mật, không gửi vào chat hoặc chụp ảnh chia sẻ.
5. Nhập mã 6 số đang hiển thị trong ứng dụng vào PetHome, chọn **Xác nhận**.
6. Khi duyệt tin hoặc sửa dữ liệu, dùng mã hiện tại từ tài khoản vừa thêm trong ứng dụng. Không dùng dãy 000000 gợi ý trong ô nhập.

Trang thiết lập hiện hiển thị khóa nhập thủ công; không cần chờ mã gửi qua SMS hoặc email. Việc kiểm tra database chỉ xác định được trạng thái liên kết, không thể xác định tên ứng dụng trên điện thoại của chủ tài khoản.
