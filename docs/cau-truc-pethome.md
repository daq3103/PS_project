# PetHome: nền tảng chung cho Shop và Trạm cứu hộ

- `/`: trang giới thiệu chung với hai khu vực ngang hàng.
- `/shop`: trang bán hàng trước đây, giữ danh mục và sản phẩm.
- `/tram-cuu-ho`: tìm thú cưng, tìm chủ và nhận nuôi.
- `/account`: tài khoản chung, chia hoạt động theo hai khu vực.
- `/admin`: chọn khu vực quản trị theo quyền của tài khoản.
- `/admin/shop`: tổng quan doanh thu, đơn hàng và kho trước đây.

Menu cấp một luôn là Shop và Trạm cứu hộ. Menu chức năng chỉ hiện khi đang ở khu vực tương ứng; trang chủ, đăng nhập và hồ sơ chung không mang menu bán hàng. Các đường dẫn sản phẩm, giỏ hàng và tin cứu hộ cũ vẫn hoạt động.

Tên hiển thị nằm ở `frontend/src/lib/brand.ts`; tiêu đề API ở `backend/app/main.py`. Gói chạy frontend mang tên `pethome-frontend`. Giữ tên thư mục `PS_project`, dự án Docker, volume và database để không vô tình chuyển sang bộ dữ liệu local khác. Không đổi khóa phiên đăng nhập hoặc lựa chọn thống kê đã lưu trên trình duyệt.

Thống kê mới ghi trang chủ vào nhóm `platform` (Trang chung), trang Shop vào `shop`. Dữ liệu lịch sử giữ nguyên nhóm tại thời điểm ghi nhận. Thay đổi này không cần migration riêng; các migration của tính năng trước vẫn cần được áp dụng khi triển khai toàn bộ phiên bản.

Chạy frontend local như trước: `npm run dev` trong `frontend`. Nếu dùng Docker, cần build lại frontend và API để có giao diện và phân nhóm thống kê mới.

## Kiểm tra

- `npm run build` trong `frontend`: đã qua, gồm kiểm tra kiểu và lint.
- `node scripts/platform-smoke.cjs` trong `qa-e2e`: đã qua tại 1440, 390 và 320 px. Dùng API giả cục bộ; kiểm tra trang chủ, chuyển Shop / Trạm cứu hộ, tab nhận nuôi, tài khoản chung, nhóm quản trị theo vai trò, chặn tài khoản thường, trạng thái tạm ngưng cứu hộ và tràn ngang. Không ghi dữ liệu thật.
- Backend: test phân loại đường dẫn thống kê, Ruff và mypy cho module analytics đã qua.
- Ảnh kiểm tra: `test-reports/screenshots/platform/`.

Docker local đã được build và thay container ứng dụng ngày 22/10/2026. API tự nâng database từ `0002` lên `0005`; bản sao lưu trước khi nâng cấp nằm trong `.local-backups/` (được Git bỏ qua). Đã kiểm tra trang chủ, Shop và Trạm cứu hộ qua `http://localhost` và `http://localhost:3000`.
