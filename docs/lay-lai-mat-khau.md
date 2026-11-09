# Lấy lại mật khẩu PetHome

## Trải nghiệm người dùng

1. Ở trang đăng nhập, chọn **Quên mật khẩu?**.
2. Nhập email đã đăng ký. Thông báo sau khi gửi giống nhau dù email có tài khoản hay không.
3. Nhập mã 6 số nhận trong email trong vòng 10 phút. Mỗi mã chỉ dùng một lần, tối đa 5 lần thử; gửi lại sẽ vô hiệu hóa mã cũ.
4. Xác minh đúng mã sẽ mở biểu mẫu đặt mật khẩu mới (nhập hai lần). Hoàn tất trong 10 phút; tải lại trang sẽ cần yêu cầu mã mới.
5. Sau khi đổi, đăng nhập lại. Mọi phiên cũ bị vô hiệu hóa ngay.

Tài khoản chỉ đăng ký bằng số điện thoại chưa có cách tự lấy lại mật khẩu vì hệ thống chưa có dịch vụ gửi SMS. Giao diện hướng dẫn liên hệ người quản trị để bổ sung email và xác minh tài khoản.

## Bật gửi email

### Gửi bằng Gmail

Đây là Gmail **của website dùng gửi thư**, chỉ cấu hình một lần. Người dùng nhập email tài khoản của họ ở trang quên mật khẩu; họ không phải cung cấp mật khẩu Gmail. Địa chỉ nhận không bắt buộc là Gmail.

1. Bật xác minh hai bước cho Gmail dùng gửi thư.
2. Tạo **Mật khẩu ứng dụng** tại https://myaccount.google.com/apppasswords, đặt tên `PetHome`.
3. Điền trực tiếp vào `.env` trên máy chạy web (không gửi mật khẩu trong chat):

```dotenv
APP_PUBLIC_URL=http://localhost
PASSWORD_RESET_EMAIL_PROVIDER=gmail
GMAIL_USER=dia-chi-gui@gmail.com
GMAIL_APP_PASSWORD=mat-khau-ung-dung-16-ky-tu
```

Hệ thống gửi từ Gmail này qua `smtp.gmail.com:465` với TLS được xác minh. Không dùng mật khẩu đăng nhập Gmail thông thường. Người nhận dùng email đã đăng ký PetHome, không bắt buộc là Gmail. Nếu Google không cho tạo mật khẩu ứng dụng, kiểm tra chính sách tài khoản hoặc dùng Resend ở phần dưới.

`http://localhost` chỉ dùng khi mở link trên chính máy đang chạy web. Khi dùng trên điện thoại hoặc máy khác, đặt `APP_PUBLIC_URL` thành tên miền HTTPS truy cập được từ thiết bị đó.

Sau khi sửa cấu hình, chạy `docker compose up -d --build --no-deps fastapi-api`. Nếu Windows chặn cổng 3000 và đã khởi động bằng file ghi đè cổng tạm, chỉ cập nhật API bằng lệnh này để giữ web qua Nginx ở cổng 80. Kiểm tra `/api/v1/auth/password-reset/config`; chỉ khi đủ cấu hình mới hiện `available: true`. Sau đó thử **Quên mật khẩu?** bằng tài khoản có email thật để kiểm tra thư đến và đặt lại mật khẩu.

Hướng dẫn Google: https://support.google.com/mail/answer/185833

### Gửi bằng Resend

Trong `.env` của **máy chạy PetHome**, điền:

```dotenv
APP_PUBLIC_URL=https://ten-mien-truy-cap-cua-ban
PASSWORD_RESET_EMAIL_PROVIDER=resend
RESEND_API_KEY=<api-key-cua-ban>
RESEND_FROM=PetHome <hello@ten-mien-da-xac-minh>
```

`APP_PUBLIC_URL` phải là địa chỉ người dùng có thể mở từ email. Với Cloudflare quick tunnel, URL thay đổi khi tunnel khởi động lại; nên dùng tên miền cố định trước khi bật tính năng này. Địa chỉ gửi phải thuộc tên miền đã xác minh với Resend. Không đưa API key vào Git hoặc giao diện. Sau khi sửa `.env`, chạy `docker compose up -d --no-deps --force-recreate fastapi-api` để API nhận biến mới. Có thể kiểm tra trạng thái tại `/api/v1/auth/password-reset/config`; `available: true` nghĩa là cấu hình cần thiết đã có, còn việc gửi thực tế vẫn phụ thuộc dịch vụ email.

Khi chưa cấu hình, trang lấy lại mật khẩu hiển thị form để xem thiết kế nhưng khóa nút gửi và nói rõ email chưa sẵn sàng. API trả 503 cho yêu cầu gửi; không tạo liên kết không thể nhận.

## Bảo vệ tài khoản

- Mã 6 số được lưu dưới dạng HMAC-SHA-256 gắn với từng yêu cầu, có khóa bí mật từ máy chủ. Mã hết hạn sau 10 phút, tối đa 5 lần thử; bộ đếm vẫn được lưu khi API trả lỗi.
- Xác minh mã thành công mới cấp token ngẫu nhiên lưu dưới dạng SHA-256, có hiệu lực 10 phút và dùng một lần. Token chỉ giữ trong bộ nhớ của trang, không đặt vào URL hay localStorage.
- Yêu cầu gửi bị giới hạn theo IP và email (email được băm trong khóa giới hạn); API không xác nhận email có tồn tại.
- Đổi mật khẩu sẽ vô hiệu hóa token đặt lại còn lại, refresh token và access token cũ. Cookie đăng nhập trên trình duyệt hiện tại cũng bị xóa.
- Token không được ghi vào log hay thống kê URL; thống kê chỉ lưu `/reset-password`, bỏ phần query.

Migration `0006` thêm bảng `password_reset_tokens` và `users.auth_version`; `0013` bổ sung mã xác minh và bộ đếm nhập sai. Các link đã cấp trước khi nâng cấp vẫn dùng được đến khi hết hạn. API áp dụng migration khi khởi động trong Docker. Kiểm tra trên database riêng: `python scripts/test_community.py tests/test_password_reset.py tests/test_gmail_delivery.py`.
