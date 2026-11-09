# Đặc điểm và tìm kiếm thú cưng

Đợt này triển khai ba phần: thông tin nhận dạng, bộ lọc tìm tin và xem ảnh rõ hơn.

## Sử dụng

- Khi đăng/sửa tin, chọn loài để xem gợi ý giống tương ứng. Có thể nhập giống khác hoặc bỏ trống khi chưa biết. ALN/ALD và một số tên giống tiếng Anh được chuẩn hóa khi lưu.
- Chọn nhiều màu lông; hoa văn, độ dài lông, giới tính, vóc dáng, tuổi, cân nặng và dấu hiệu nhận dạng đều không bắt buộc. Các thông tin này dùng cho cả tin thất lạc, nhặt được và nhận nuôi.
- Tìm từ khóa có hoặc không dấu, ví dụ `ALN xam duoi cut`. Các từ được kết hợp để thu hẹp kết quả. Bộ lọc giống chỉ đối chiếu trường giống, không dùng mô tả bài viết.
- Khi lọc nhiều màu, tin phải có đủ các màu đã chọn. Các điều kiện khác cũng được kết hợp. Chọn “Chưa rõ” để tìm tin chưa có đặc điểm tương ứng.
- Khoảng ngày tính theo giờ Việt Nam, gồm cả ngày kết thúc. Dùng lần thấy cuối cho tin thất lạc, thời điểm nhặt được cho tin nhặt được và ngày đăng cho tin nhận nuôi. Tin không có thời điểm tương ứng bị loại khi lọc ngày.
- Gửi bộ lọc mới sẽ về đầu danh sách. Chuyển trang giữ nguyên bộ lọc. Xóa bộ lọc giữ nguyên mục thất lạc/nhặt được/nhận nuôi đang xem.
- Khi đăng tin, chọn “Làm ảnh đại diện” để đưa một ảnh lên đầu. Trang chi tiết và phần duyệt tin cho mở toàn ảnh, phóng to, cuộn xem, chuyển ảnh bằng nút hoặc phím mũi tên, đóng bằng Escape/nút đóng.
- Thẻ tin hiển thị trạng thái để phân biệt tin đang tìm, đã đoàn tụ và đã nhận nuôi.

## Tương thích và triển khai

- Migration `0005_pet_traits.py` thêm `pet_details` và `search_text` vào `community_posts`, cùng chỉ mục GIN cho thuộc tính. `search_text` dùng nội bộ và không có trong dữ liệu công khai.
- Tin cũ giữ nguyên nội dung, ảnh và giống/màu nhập tự do. Migration tạo nội dung tìm kiếm không dấu từ các trường cũ và mở rộng các tên viết tắt đã định nghĩa. Không suy đoán màu/giống từ ảnh.
- Thuộc tính chưa có trong tin cũ hiển thị “Chưa rõ”. Muốn tin cũ xuất hiện khi lọc màu có cấu trúc, người đăng cần chọn màu rồi lưu lại; vẫn có thể tìm màu cũ bằng từ khóa.
- Nơi xử lý tạo/sửa tin cập nhật nội dung tìm kiếm; sửa đặc điểm/đổi ảnh đại diện tiếp tục đưa tin về chờ duyệt như sửa nội dung khác. Giới hạn ảnh, phân quyền và quyền xem liên hệ tiếp tục được áp dụng.
- Triển khai cần sao lưu dữ liệu, chạy `alembic upgrade head` đến `0005`, rồi cập nhật ứng dụng và worker đồng bộ. Chưa chạy migration này trên database website trong đợt phát triển.
- Tra cứu văn bản hiện dùng chuỗi đã chuẩn hóa và tham số truy vấn an toàn. Khi số tin tăng lớn, cần đo truy vấn thực tế để bổ sung chỉ mục tìm văn bản phù hợp.

## Phạm vi tiếp theo

Gợi ý ghép tin thất lạc/nhặt được, lưu tin và đăng ký nhận thông báo theo điều kiện tìm kiếm thuộc đợt sau.

## Kiểm chứng ngày 22/10/2026

- Build Next.js và lint đạt; Ruff và mypy cho module cứu hộ/thống kê đạt.
- 23 kiểm thử backend đạt trên database PostgreSQL tạm riêng. Migration được chạy xuống/lên và kiểm tra nội dung tin, ảnh, dữ liệu giống cũ cùng nội dung tìm kiếm không dấu.
- 4 luồng Playwright với API thật đạt trên desktop 1440px và mobile 390px: đăng tin, đọc lại đặc điểm ở biểu mẫu sửa, nhiều màu, giống viết tắt, chọn ảnh đại diện, duyệt, bộ lọc, khoảng ngày sai, xem ảnh, đoàn tụ và nhận nuôi. Việc lưu thay đổi đặc điểm được kiểm chứng trong bộ test backend.
- Kiểm tra thêm 320px và 768px đạt: bộ lọc/ảnh không tràn trang, phóng to và đóng bằng Escape, trả lại vị trí bàn phím.
- Chỉ database và tài khoản thử nghiệm được dùng; ứng dụng Docker và database website chưa được nâng cấp trong đợt này.
