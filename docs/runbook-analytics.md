# Theo dõi truy cập và hiệu năng

Dashboard: `/admin/analytics`, chỉ tài khoản `owner` có quyền đọc cả API và giao diện điều hướng.
Hệ thống tự thu thập, không gửi dữ liệu đến Google Analytics hay dịch vụ analytics bên ngoài.

## Triển khai

- Backend cần `psutil`, frontend cần `web-vitals`; dependencies đã khai báo trong source.
- Backup database theo quy trình vận hành, chạy `alembic upgrade head` để tạo bảng `analytics_events` qua revision `0004`, sau đó cập nhật API, worker và frontend.
- `ANALYTICS_ENABLED=true` bật thu thập lượt xem và bộ đếm API. Đổi thành `false` rồi khởi động lại API để ngưng; frontend đang mở cần tải lại để nhận cấu hình mới.
- `ANALYTICS_RETENTION_DAYS=90` (30–365): worker xóa sự kiện cũ mỗi ngày lúc 03:45 theo múi giờ worker. Khung báo cáo hỗ trợ 1/7/30/90 ngày, theo ngày lịch Việt Nam.
- Rollback riêng analytics: dừng tracker/worker phiên bản mới, `alembic downgrade 0003` (xóa dữ liệu analytics), chạy lại phiên bản ứng dụng tương thích. Không downgrade khi frontend mới đang gửi sự kiện.

## Ý nghĩa số liệu

- Lượt xem: lần mở hoặc chuyển pathname. Thay đổi query/filter trên cùng pathname không tăng lượt xem. Retry cùng event ID không tăng bộ đếm.
- Khách: số mã trình duyệt khác nhau trong kỳ, không phải số người xác minh. Mã lưu localStorage tối đa 90 ngày, khi lưu DB được HMAC bằng JWT secret với namespace analytics; thay secret làm thay đổi cách nhận diện.
- Phiên: mã dùng chung các tab; hết hạn sau 30 phút không có sự kiện. Heartbeat chỉ gửi khi tab hiển thị và có hoạt động trong 5 phút vừa qua.
- Đang hoạt động: số phiên có pageview/heartbeat trong 5 phút, dựa Redis cache. Mỗi khu vực đếm phiên đã hoạt động trong khu đó, một phiên có thể xuất hiện ở cả hai khu; số toàn website khử trùng lặp.
- Nguồn: nhóm referrer đầu phiên (trực tiếp/nội bộ/tìm kiếm/mạng xã hội/website khác). Không lưu URL referrer, không triển khai attribution quảng cáo, địa lý hay UTM.
- Thiết bị: suy đoán từ user agent phía trình duyệt; không lưu user agent gốc.
- Trang được gộp theo route template: `/p/[product]`, `/tram-cuu-ho/[post]`... Không lưu slug, query, fragment, form, IP, email, số điện thoại hoặc liên kết tracking vào bảng analytics.
- Theo dõi storefront và khu tài khoản, loại admin/đường dẫn lạ. DNT, GPC và localStorage `petshop:analytics:optout=1` ngưng tracker. Đây là phép đo phía trình duyệt; bot, chặn tracking, đổi thiết bị/xóa storage có thể làm lệch số khách.
- LCP/INP/CLS/TTFB dùng `web-vitals` đóng gói trong frontend, không tải script Google. p75 tính từ các mẫu nhận được của tài liệu thực, không xem chuyển trang SPA là lượt đo Web Vitals mới; trình duyệt không hỗ trợ/chưa tương tác có thể chưa có mẫu.

## Server và API

- Owner được xem kiểm tra kết nối PostgreSQL, Redis cache, Redis queue, độ trễ probe, queue depth và sự tồn tại heartbeat ARQ mặc định.
- CPU/RAM hệ thống là tài nguyên mà tiến trình API nhìn thấy (có thể là host Docker). RAM container hiển thị riêng khi đọc được cgroup v2. RSS/uptime thuộc worker API phục vụ request, không phải cộng dồn bốn worker. Disk là filesystem API, không đại diện cho mọi volume database.
- Chưa có agent host/Prometheus để đo riêng từng container Next/Nginx, mạng, I/O hay lưu lịch sử tài nguyên VPS. Không mount Docker socket vào API.
- Middleware ghi số request, 4xx/5xx, latency và route template; bỏ endpoint analytics để dashboard không tự tăng lưu lượng đo. 404 gộp `/unmatched`, không ghi URL request hoặc payload.
- Cửa sổ gồm phút hiện tại và 14 phút trước; p95 là cận trên bucket histogram, không phải phân vị chính xác của từng request. Redis cache bị xóa/evict thì bộ đếm thời gian thực mất; lịch sử trình duyệt trong PostgreSQL vẫn còn.
- Lỗi telemetry không làm request bán hàng thất bại; middleware có timeout 50 ms và circuit breaker 30 giây. Dashboard hiển thị lỗi dữ liệu, không biến trạng thái không đo được thành hệ thống khỏe.
- Cảnh báo trong dashboard: CPU/RAM/disk >=85%, API 5xx >=1%, dịch vụ probe lỗi. Chưa có cảnh báo email/SMS hoặc giám sát ngoài hệ thống khi cả API ngừng.

## Kiểm thử

`python scripts/test_community.py` tạo database ngẫu nhiên riêng, nâng migration, chạy toàn bộ tests và kiểm tra downgrade/upgrade rồi xóa đúng database đã tạo. Dùng Redis database riêng (ví dụ 15) cho môi trường QA; không flush Redis vận hành.

Kiểm thử trình duyệt cần xác minh navigation SPA tăng đúng 1 lượt, query không tăng lượt, admin không gửi event, DNT/optout, mobile không tràn và API owner trả 403 cho tài khoản khác.

Tài liệu tham khảo triển khai: [web-vitals](https://github.com/GoogleChrome/web-vitals), [psutil](https://psutil.readthedocs.io/stable/index.html).

## Xác minh ngày 21/10/2026

- 18 bài kiểm thử backend qua, gồm 6 bài analytics; có vòng migration lên `0004`, xuống `0002` và lên lại trên database ngẫu nhiên riêng.
- Hai luồng trình duyệt desktop/mobile qua trên API và database QA thật: pageview SPA, query không tăng lượt, dashboard/đổi bộ lọc, kết nối dịch vụ, DNT và từ chối quyền khách hàng.
- Frontend production build, TypeScript, ESLint, backend Ruff và mypy cho analytics/cứu hộ đều qua.
- Migration và image mới chưa áp dụng lên stack shop đang vận hành. Dữ liệu trong ảnh chụp là dữ liệu QA.
