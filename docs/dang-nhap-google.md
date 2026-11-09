# Tài khoản PetHome

Đăng ký mới dùng tên tài khoản (3–40 ký tự, bắt đầu bằng chữ; gồm chữ, số, dấu gạch dưới) và mật khẩu. Tên không phân biệt hoa thường. Google là cách đăng nhập thứ hai. Email và số điện thoại cũ vẫn dùng để đăng nhập tài khoản đã tồn tại, giữ nguyên dữ liệu.

Hồ sơ có liên kết Google, xác minh email khôi phục, số điện thoại và liên kết sổ địa chỉ nhận hàng. Email chỉ được cập nhật sau khi nhập đúng mã trong hộp thư. Tài khoản chưa có email khôi phục cần liên hệ quản trị nếu quên mật khẩu. Số điện thoại và địa chỉ được bổ sung khi cần đặt hàng/nhận nuôi. Không dùng SMS.

## Bật Google

1. Trên https://console.cloud.google.com/apis/credentials tạo dự án, cấu hình Google Auth Platform (tên ứng dụng, email hỗ trợ, đối tượng External; thêm tài khoản thử nếu ở chế độ Testing).
2. Tạo OAuth Client ID loại **Web application**. Thêm Authorized JavaScript origins `http://localhost` và `http://localhost:3000`; khi triển khai thêm origin HTTPS thật. Không thêm đường dẫn vào origin. Luồng Google Identity Services này không cần client secret trong trình duyệt.
3. Điền `GOOGLE_CLIENT_ID=...apps.googleusercontent.com` trong `.env` rồi chạy `docker compose up -d --no-deps fastapi-api`.
4. Thử nút Google tại `/login` hoặc `/register`. Nếu email đã thuộc tài khoản khác, đăng nhập tài khoản đó, vào Hồ sơ và liên kết Google. Hệ thống không tự gộp theo email. Tài khoản quản trị vẫn cần mã TOTP.

Google phải được cấu hình bởi chủ dự án; địa chỉ Gmail gửi thư và mật khẩu ứng dụng SMTP không thay thế Client ID này.

## Sửa lỗi 400: origin_mismatch

Trong Google Cloud → Google Auth Platform → Clients, mở đúng Web client trùng `GOOGLE_CLIENT_ID` của API. Thêm origin của trang đang mở vào **Authorized JavaScript origins**: gồm giao thức, tên miền và cổng nếu có, không có đường dẫn `/login` hay dấu `/` cuối. `http://localhost`, `http://localhost:3000` và tên miền HTTPS là các origin riêng.

Nếu dùng Cloudflare Tunnel với tên miền ngẫu nhiên, mỗi lần tên miền đổi phải thêm origin mới; nên dùng hostname cố định cho môi trường test. Lưu cấu hình, đợi Google áp dụng rồi mở lại trang và thử đăng nhập. Không thay Client ID bằng ID của dự án khác, không bỏ kiểm tra ID token/nonce để né lỗi. Cấu hình này thuộc Google Cloud, không thể sửa chỉ bằng commit mã nguồn. Chỉ đánh dấu pass sau khi đăng nhập thật trên đúng địa chỉ đang test.

Tài liệu: https://developers.google.com/identity/gsi/web/guides/verify-google-id-token
