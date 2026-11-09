# Xác thực quản trị theo phiên

## Cách sử dụng

- Quản trị viên (`owner`) đã thiết lập ứng dụng xác thực: nhập email/mật khẩu, rồi nhập mã 6 số ngay tại trang đăng nhập. Khi chưa nhập mã hợp lệ, website chưa cấp phiên đăng nhập mới.
- Sau khi đăng nhập và xác minh thành công, duyệt bài, sửa sản phẩm, xử lý đơn hoặc cấp quyền không hỏi lại mã trong cùng phiên.
- Nhân viên được cấp quyền đăng nhập bằng mật khẩu, không cần mã hai bước. Quyền chăm sóc khách hàng mới được duyệt tin; quyền kho không tự có quyền này.
- Quản trị viên chưa thiết lập được chuyển tới Cài đặt bảo mật. Phiên mới chỉ dùng để hoàn tất thiết lập, chưa được thao tác dữ liệu quản trị.
- Đăng xuất thu hồi phiên trong database. Đổi mật khẩu, khôi phục xác thực, thay đổi quyền hoặc hết hạn phiên cũng làm mất quyền truy cập tương ứng. Phiên đăng nhập vẫn có thời hạn cấu hình; không phải truy cập vĩnh viễn.

## Cơ chế

Migration `0009` thêm `refresh_tokens.mfa_verified`, mặc định false, nên phiên quản trị cũ chưa xác minh phải đăng nhập lại. Access token mới chứa ID của phiên; backend kiểm tra phiên chưa hết hạn/chưa bị thu hồi và trạng thái xác minh của quản trị viên. Không dùng localStorage hay một cờ do trình duyệt tự khai báo để quyết định đã xác minh.

Làm mới phiên giữ trạng thái xác minh trong bản ghi kế tiếp. Frontend tự khôi phục phiên khi access token hết hạn; các tab phối hợp bằng Web Locks nếu trình duyệt hỗ trợ để giảm việc đồng thời quay vòng cookie. Middleware chỉ ngăn cache; server layout kiểm tra danh tính và chuyển hướng theo địa chỉ đang truy cập. API vẫn là nơi kiểm tra quyền thật.

Các endpoint thiết lập được miễn yêu cầu phiên đã xác minh, nhưng vẫn yêu cầu tài khoản quản trị đã đăng nhập bằng mật khẩu. Mã xác thực đăng nhập và mã xác nhận thiết lập có giới hạn số lần thử theo tài khoản. Không thay khóa đang liên kết hoặc tắt xác thực của tài khoản hiện có trong quá trình cập nhật này.

## Kiểm tra và triển khai

Đã chạy bộ test trên database ngẫu nhiên, tách khỏi dữ liệu cửa hàng: 27 test xác thực, phân quyền, khôi phục mật khẩu, danh mục, cứu hộ và thống kê đạt; migration lên/xuống/lên đạt. Test mới bao gồm không cấp cookie trước khi xác minh, từ chối mã sai, thao tác lặp lại không gửi mã, giữ xác minh khi làm mới phiên, chặn token sau đăng xuất và giới hạn quyền nhân viên.

Đã tạo bản sao database trước migration tại `.local-backups/pethome-before-mfa-0009.dump`, được loại khỏi Git. Không ghi khóa bí mật hoặc mã xác thực thật vào báo cáo/test.

Kiểm thử giao diện giả lập đã qua: yêu cầu mã trước khi cấp cookie, hiển thị lỗi mã sai, đăng nhập với mã hợp lệ, khôi phục phiên sau khi xóa access cookie để mô phỏng hết hạn, rồi tạo danh mục/sản phẩm mà không có hộp hỏi mã theo thao tác. Bản Linux hoàn chỉnh đã build thành công; migration 0009 và bản mới đã được áp dụng lên Docker với `docker-compose.4gb.yml`. Kiểm tra sau triển khai: trang đăng nhập local/public trả 200, người chưa đăng nhập vào `/admin` được chuyển về `/login` và giữ nguyên hostname công khai. Không thử đăng nhập bằng mật khẩu hay mã xác thực thật qua đường hầm công khai.

Để tránh build chiếm nhiều RAM trên Windows, có `qa-e2e/scripts/safe-build.py` chạy một worker, giới hạn heap Node và dừng khi RAM trống thấp. Bản Docker Linux cũng có thể build trong container giới hạn bộ nhớ rồi commit kết quả sang image cục bộ `pethome-frontend-compiled-mfa:local`; `frontend/Dockerfile.runtime` đóng gói standalone từ image đó mà không biên dịch lần nữa. Luồng `docker compose build` thông thường vẫn sử dụng `frontend/Dockerfile`.
