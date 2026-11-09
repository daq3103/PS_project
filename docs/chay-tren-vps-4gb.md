# PetHome trên máy chủ RAM 4 GB

Cấu hình thử nghiệm: 2 vCPU trở lên, RAM 4 GB, SSD còn trống đủ dữ liệu và bản sao lưu. Đây là ngân sách chạy ứng dụng, chưa phải cam kết sức tải.

Chạy bằng hai file Compose, từ thư mục project:

```powershell
docker compose -f docker-compose.yml -f docker-compose.4gb.yml up -d --no-build
```

Cần build image worker mới trước lần dùng đầu để nhận WORKER_MAX_JOBS. Nên build image trên máy riêng hoặc CI, rồi chuyển sang VPS; không build Next.js đồng thời phục vụ khách trên máy ít RAM.

Các giới hạn container cộng lại là 2688 MiB, để dành phần còn lại cho Linux và dự phòng. API có 2 tiến trình; mỗi tiến trình tối đa 7 kết nối database, worker tối đa 4. PostgreSQL có giới hạn 60 kết nối và giảm bộ nhớ cho mỗi thao tác truy vấn. Worker xử lý tối đa 3 việc đồng thời. Redis cache giảm dung lượng, Redis hàng đợi giữ chính sách không tự xóa công việc khi đầy.

Giới hạn bộ nhớ không phải lượng RAM đã đặt trước và không đảm bảo RAM thực tế luôn thấp. Khi vượt giới hạn, dịch vụ có thể bị dừng vì thiếu bộ nhớ; cần theo dõi số lần khởi động lại, bộ nhớ, hàng đợi và dung lượng dữ liệu.

Mỗi lần up/recreate phải dùng cả hai file để giữ cấu hình 4 GB. Muốn quay về cấu hình gốc:

```powershell
docker compose -f docker-compose.yml up -d --no-build
```

Trên Windows, Docker/WSL còn có chi phí bộ nhớ ngoài container. Bài kiểm thử `qa-e2e/scripts/safe-load.py` chỉ chạy nếu Windows còn trống ít nhất 4 GiB và tự dừng khi dưới 2,5 GiB; kiểm tra lại tài nguyên sau khi Docker đã khởi động. Bài này chỉ thử đọc tối đa 5 yêu cầu/giây, không đại diện tải mua hàng, upload ảnh hoặc người dùng thực tế đầy đủ.
