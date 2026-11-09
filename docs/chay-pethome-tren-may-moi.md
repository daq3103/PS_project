# Chạy PetHome trên máy mới

Máy mới chỉ cần Docker Desktop có Docker Compose, hỗ trợ Linux containers. Trên Windows, bật ảo hóa và WSL 2 khi Docker Desktop yêu cầu. Không cần cài Node.js, Python hay PostgreSQL riêng; chúng nằm trong image/container.

## Cài mới, chưa cần dữ liệu cũ

1. Cài và mở Docker Desktop. Đợi Docker báo đã chạy.
2. Chép toàn bộ thư mục project sang máy mới (hoặc clone repository). Giữ `docker-compose.yml`, `frontend/` (gồm `frontend/public/`), `backend/` và `nginx/` trong cấu trúc hiện tại.
3. Trong thư mục gốc, chạy `Copy-Item .env.example .env`, rồi điền mật khẩu và khóa bí mật của riêng môi trường này. `.env` không nằm trong Git.
4. Mở PowerShell trong thư mục gốc rồi chạy:

   ```powershell
   docker compose up -d --build
   docker compose ps
   ```

5. Mở `http://localhost` (qua Nginx) hoặc `http://localhost:3000` (trực tiếp Next.js). Trang chủ phải hiện PetHome, Shop và Trạm cứu hộ. Lần build đầu cần Internet để lấy image và thư viện, đồng thời cần các cổng 80, 3000, 8000 chưa bị ứng dụng khác chiếm.

Container API tự chạy migration. Nếu chỉ chuyển mã nguồn, database mới sẽ rỗng; cần tạo tài khoản/quản trị và dữ liệu bán hàng trên máy mới.

## Muốn giữ dữ liệu từ máy cũ

Mang thêm **bản sao PostgreSQL**, **volume ảnh cứu hộ** (`community_uploads`) và file `.env`/các khóa bí mật tương ứng. Image Docker hoặc source code không chứa database và ảnh trong volume. Nếu còn công việc nền chưa xử lý, phải kiểm tra cả hàng đợi Redis trước khi ngắt máy cũ.

Trên máy này, bản sao PostgreSQL trước lúc nâng lên `0005` đã được lưu tại `.local-backups/pethome_before_upgrade_2026-10-22.dump`. Bản đó phản ánh dữ liệu ở thời điểm sao lưu, không gồm thay đổi phát sinh sau đó. Khi chuyển máy, tạo bản sao **mới nhất** rồi phục hồi vào database trống trước khi khởi động API. Không gửi `.env` hoặc bản sao database qua Git công khai.

Khi cập nhật code ở máy mới, chạy lại `docker compose up -d --build`. Lệnh `docker compose build` chỉ tạo image; container đang phục vụ web vẫn dùng image cũ cho tới khi chạy `up` để thay nó.
