# Rà soát bảo mật và vận hành PetHome

## Cập nhật khắc phục

Thay đổi chính sách sau lần rà soát: theo yêu cầu chủ project, xác thực hai bước chỉ áp dụng cho quản trị viên (`owner`) ở bước đăng nhập, được ghi nhớ theo phiên ở backend. Nhân viên không cần mã, nhưng vẫn bị giới hạn theo quyền đã cấp. Mô tả yêu cầu mã trên từng thao tác bên dưới là thiết kế trước đây, đã được thay thế bằng chính sách theo phiên trong migration 0009. Xem `docs/phan-quyen-nhan-vien.md`.

Đã sửa trong mã nguồn và kiểm thử ba mục ưu tiên đầu:

- Đơn hàng lưu dấu nhận diện phiên khách và nội dung yêu cầu; trả lại đơn chỉ khi đúng chủ và đúng yêu cầu. Khóa giao dịch ngăn hai lần gửi đồng thời tạo hai đơn. Đơn cũ chưa có dữ liệu kiểm chứng sẽ từ chối gửi lại thay vì trả thông tin; khách vẫn xem đơn bằng luồng xem/tra cứu đơn hiện có.
- API công khai chỉ đọc sản phẩm đang bán thuộc danh mục đang dùng, kể cả chi tiết/ảnh/tồn kho. Danh sách quản trị chuyển sang API cần quyền nhân viên.
- Mã hai bước được kiểm tra thêm trên các API ghi danh mục, sản phẩm và biến thể; giao diện có hộp nhập mã tương ứng.

Migration 0008 bổ sung hai cột nullable cho đơn hàng. Kiểm thử trên database riêng: ba test bảo mật/phân quyền đã qua; migration lên/xuống/lên cũng đã qua. Đã tạo bản sao local trước migration ở `.local-backups/pethome-before-security-0008.dump` và kiểm tra đọc được danh mục bản sao; chưa coi đây là quy trình sao lưu tự động hay bài thử khôi phục đầy đủ.

Các mục HTTPS/IP, sao lưu định kỳ, giám sát, tích hợp dịch vụ thật và email bên dưới vẫn còn phải triển khai/cấu hình.

Phạm vi: đọc mã nguồn, cấu hình triển khai và gọi API chỉ đọc trên Docker local. Không thực hiện khai thác, tạo đơn, gửi email hoặc thay đổi dữ liệu thật. Đây không phải kiểm thử xâm nhập toàn diện hay quét lỗ hổng thư viện.

## Ưu tiên cao

### 1. Trả đơn cũ theo mã chống tạo trùng nhưng không kiểm tra chủ sở hữu

`backend/app/modules/order/checkout.py:92`: tìm đơn chỉ bằng `idempotency_key`, sau đó trả `OrderOut` ngay, trước khi kiểm tra người gửi. Khách biết hoặc tái sử dụng khóa của đơn khác có thể nhận thông tin đơn đó. Khóa được phép là chuỗi do khách tự nhập, không phải thông tin xác thực. Chưa khai thác trên dữ liệu thật.

Khắc phục: gắn khóa với người dùng/phiên khách và kiểm tra quyền trước khi trả đơn; đối chiếu nội dung yêu cầu để từ chối tái sử dụng khóa cho dữ liệu khác. Kiểm thử bằng hai tài khoản và hai phiên khách độc lập.

### 2. API công khai chưa giới hạn sản phẩm đang bán

`backend/app/modules/catalog/router.py`: các API danh sách, chi tiết theo ID/đường dẫn, ảnh và tồn kho không yêu cầu đăng nhập. `service.py:106` chỉ lọc trạng thái khi khách truyền bộ lọc, cho phép yêu cầu `status=draft` hoặc bỏ lọc để lấy mọi trạng thái. Điều này làm sản phẩm nháp/ẩn không thực sự riêng tư.

Kiểm tra local: truy vấn sản phẩm nháp không đăng nhập trả HTTP 200; hiện không có sản phẩm nháp trong kết quả kiểm tra. Khả năng đọc nháp được xác nhận từ mã nguồn, chưa quan sát một bản ghi nháp thật bị lộ.

Khắc phục: API công khai luôn giới hạn sản phẩm đang bán và danh mục đang dùng; tách API quản trị có kiểm tra quyền, bao gồm ảnh/tồn kho và chi tiết sản phẩm.

### 3. Xác thực hai bước chưa bao phủ thao tác quản trị danh mục/sản phẩm

`backend/app/core/staff_totp.py:26` chỉ áp dụng cho đường dẫn bắt đầu `/api/v1/admin`. Trong khi tạo/sửa danh mục, sản phẩm và biến thể nằm ở `/api/v1/categories`, `/api/v1/products`, `/api/v1/variants`. Các API này vẫn kiểm tra quyền quản trị viên, nhưng không kiểm tra mã hai bước như những thao tác quản trị khác.

Khắc phục: dùng dependency xác thực hai bước cho mọi thao tác quản trị nhạy cảm, thay vì quyết định bằng tiền tố URL; đồng bộ frontend. Đây không phải lỗi cho khách vãng lai quyền sửa sản phẩm.

### 4. Bản đang dùng cấu hình phát triển khi có truy cập công khai

`.env` có `APP_ENV=development`; `backend/app/core/cookies.py:15` vì vậy không đặt cờ Secure cho cookie đăng nhập. Kiểm tra cookie CSRF qua API local cũng cho thấy thiếu Secure. Nginx mở HTTP cổng 80 trên mọi địa chỉ máy.

Khắc phục: cấu hình triển khai HTTPS riêng với cookie Secure, giới hạn đường vào origin phù hợp và tên miền cố định. Không chỉ đổi APP_ENV trong bản local HTTP vì có thể làm đăng nhập local ngừng hoạt động.

## Vận hành cần hoàn thiện

### 5. Thanh toán và vận chuyển vẫn giả lập

`backend/app/modules/order/checkout.py` dùng `MockGHNProvider`; `backend/app/worker/tasks.py` dùng `MockVietQRProvider` và `MockGHNProvider`. Mã QR được dựng bằng địa chỉ dịch vụ giả lập. Không coi trạng thái chạy thành công của các tác vụ này là bằng chứng ngân hàng/đơn vị vận chuyển đã tiếp nhận.

Khắc phục: cấu hình nhà cung cấp thật, xác minh thông báo thanh toán, đối soát số tiền và thử nghiệm đầy đủ trước khi nhận giao dịch thật. Hiển thị rõ chế độ thử nghiệm trong thời gian chưa tích hợp.

### 6. Chưa có bằng chứng sao lưu tự động và khôi phục thành công

`scripts/backup_pg.sh` mới là khung pg_dump cho máy chủ. Compose không định nghĩa lịch sao lưu. Script chưa sao lưu volume ảnh cứu hộ, chưa có quy trình khôi phục hoặc kiểm tra bản sao. Chưa kiểm tra lịch tác vụ ngoài repository nên không kết luận máy hoàn toàn không có sao lưu.

Khắc phục: sao lưu cơ sở dữ liệu và ảnh ra nơi lưu khác máy, quản lý thời gian giữ bản sao, cảnh báo khi thất bại và thử khôi phục trên môi trường riêng.

### 7. Kiểm tra sức khỏe chưa phản ánh khả năng phục vụ

`backend/app/main.py` trả healthz/readyz bằng chuỗi cố định; không thử kết nối cơ sở dữ liệu hoặc hàng đợi. Compose chỉ có healthcheck cho PostgreSQL. Container còn chạy không chứng minh API, worker hoặc tác vụ nền hoạt động đúng.

Khắc phục: readiness có timeout cho các phụ thuộc quan trọng, kiểm tra worker và cảnh báo lỗi tác vụ. Bổ sung đối soát công việc quan trọng: bước checkout đưa việc vào hàng đợi qua BackgroundTasks, có khoảng trống mất việc nếu tiến trình dừng sau khi lưu đơn; cần cơ chế lưu việc cùng giao dịch hoặc tác vụ đối soát đầy đủ.

### 8. Địa chỉ IP qua đường hầm cần xử lý đúng

Nginx luôn ghi đè X-Forwarded-For bằng địa chỉ kết nối trực tiếp. Khi đi qua cloudflared, đây có thể là địa chỉ container đường hầm. `client_ip()` còn loại các hop nằm trong dải Docker tin cậy nên giới hạn theo IP có thể gộp nhiều khách thành một nhóm.

Khắc phục: xác định chính xác các proxy được tin cậy, lấy IP khách từ Cloudflare chỉ trên đường vào đã xác minh, chặn đường vào giả mạo header. Kiểm thử bằng hai khách qua đường hầm; chưa kiểm chứng hai IP thật trong lần rà soát này.

### 9. Email lấy lại mật khẩu chưa cấu hình

Lần kiểm tra trước xác nhận thiếu APP_PUBLIC_URL, RESEND_API_KEY và RESEND_FROM; nút gửi được khóa đúng theo trạng thái cấu hình. Cần thiết lập gửi email, địa chỉ website ổn định và thử nhận thư thật trước khi mở chức năng.

## Những nền tảng đã có

Đã có kiểm tra quyền phía backend, chống giả mạo yêu cầu qua cookie, cookie đăng nhập HttpOnly, mật khẩu băm, liên kết đặt lại mật khẩu dùng một lần và vô hiệu hóa phiên cũ. PostgreSQL/Redis không xuất cổng ra host trong Compose. Các cơ chế này có ích nhưng không thay thế việc sửa các phát hiện ở trên.

## Thứ tự triển khai đề xuất

1. Sửa quyền trả đơn cũ và quyền xem sản phẩm nháp.
2. Bao phủ xác thực hai bước, cấu hình HTTPS và nhận diện IP đúng.
3. Tự động sao lưu, thử khôi phục, healthcheck/cảnh báo và đối soát tác vụ.
4. Tích hợp thanh toán/vận chuyển/email thật rồi kiểm thử luồng mua hàng và khôi phục tài khoản.
