# Phân quyền nhân viên PetHome

Trang **Quản trị → Tổng quan** là điểm vào chung. Chủ nền tảng thấy lượt truy cập hôm nay, khách đang truy cập, đơn chờ xử lý, tin chờ duyệt, tình trạng hệ thống và các việc cần ưu tiên. Chi tiết được mở tại từng khu vực, không dồn mọi biểu mẫu lên trang đầu.

Menu gồm **Điều hành → Trạm cứu hộ → Shop → Chăm sóc khách hàng → Hệ thống**. Các nhóm được thu gọn; nhóm chứa trang đang xem tự mở. Nhân viên chỉ thấy các nhóm và chức năng được cấp. Tài khoản/đăng xuất nằm cố định ở cuối thanh bên trên máy tính; menu điện thoại cũng có nút đăng xuất.

Quản trị viên mở **Hệ thống → Nhân viên & phân quyền**, tìm tài khoản đã đăng ký bằng tên tài khoản, họ tên, email hoặc số điện thoại rồi chọn một hoặc nhiều nhóm quyền. Tìm tên tài khoản không phân biệt chữ hoa/thường; kết quả hiển thị tên tài khoản để nhận diện đúng người:

| Nhóm quyền | Phạm vi |
| --- | --- |
| Kho & giao hàng | Đơn hàng, đóng gói, vận đơn, lô hàng, điều chỉnh tồn và báo cáo bán hàng |
| Chăm sóc khách hàng Shop | Đơn hàng, yêu cầu hỗ trợ, duyệt đánh giá sản phẩm |
| Quản lý trạm cứu hộ | Hồ sơ các bé, tiếp nhận, phân công, lịch hẹn, tin cứu hộ, nhận nuôi và báo cáo trạm |
| Chăm sóc cứu hộ | Các bé, tin báo và công việc được giao; không tự đọc toàn bộ hồ sơ trạm |
| Tài chính cứu hộ | Sổ thu chi, đối soát và đề nghị chi của trạm; không tự đọc hồ sơ chăm sóc |
| Quản lý nền tảng (không cấp quyền) | Đầy đủ quyền vận hành Shop, trạm cứu hộ, sản phẩm, danh mục, khuyến mãi, đối soát, số liệu hệ thống và lịch sử trạm. Không được đọc danh sách/lịch sử phân quyền nhân viên hay cấp quyền. |

Các nhóm được cộng lại khi cùng được chọn. Bỏ tất cả đưa tài khoản về quyền khách hàng. Trang nhân viên không cấp quyền quản trị viên hoặc sửa chính mình. Tài khoản bị khóa không thể được nâng quyền. Thay đổi quyền có ghi lịch sử, thu hồi phiên cũ và yêu cầu người nhận đăng nhập lại.

**Chỉ chủ nền tảng** được quản lý nhân viên và cấp quyền. Nhóm `platform_manage` cho phép vận hành toàn bộ chức năng mà không biến tài khoản thành chủ nền tảng; các nhân viên chưa có nhóm này giữ nguyên phạm vi được cấp. Thiết lập TOTP dành riêng cho tài khoản chủ nền tảng vẫn chỉ tác động tới chính chủ; nhân viên xem thông tin tài khoản tại Cài đặt.

Giao diện nhân viên có trang **Công việc của bạn**. Chỉ lấy số liệu Shop khi có quyền Shop, và số liệu tin/nhận nuôi khi có quyền quản lý trạm. Nhân viên chăm sóc hoặc tài chính trạm nhận liên kết vào đúng phần được giao; số liệu chưa có không được hiển thị thành số 0. Gõ trực tiếp đường dẫn ngoài quyền hiển thị thông báo chưa được cấp quyền. API vẫn kiểm tra quyền từng yêu cầu.

Tổng quan chỉ cập nhật khi mở trang hoặc bấm **Làm mới**. Hỏng một nguồn số liệu không làm mất các nguồn còn lại; trang ghi rõ mục nào chưa tải được. Khách truy cập là ước tính theo thiết bị. Tình trạng hệ thống phản ánh các kiểm tra kết nối hiện có; bộ nhớ xử lý web là mức dùng trong giới hạn container dịch vụ web, không phải toàn bộ RAM máy chủ. Báo cáo hiệu năng chi tiết nằm ở **Hệ thống → Truy cập & hiệu năng**.

Quản trị viên xác minh hai bước một lần khi đăng nhập. Trạng thái gắn với phiên; làm mới phiên không hỏi lại mã. Đăng xuất, đổi mật khẩu, khôi phục xác thực hoặc thu hồi phiên làm phiên cũ hết hiệu lực. Quản trị viên chưa thiết lập được đưa tới **Cài đặt bảo mật** để hoàn tất. Nhân viên đăng nhập bằng mật khẩu và không cần thiết lập mã của quản trị viên.

## Kiểm tra giao diện bằng dữ liệu giả

Chạy `node qa-e2e/scripts/admin-workspace-smoke.cjs` sau khi build image `pethome-admin-ui:local`. Script dùng máy chủ API giả và container riêng giới hạn 256 MB; không tạo tài khoản hoặc ghi vào database thật. Kiểm tra chủ nền tảng, cả năm nhóm quyền, tài khoản có nhiều quyền, đường dẫn ngoài quyền, lỗi một nguồn số liệu và màn hình điện thoại/máy tính. Ảnh lưu trong `PetHome-screenshots/`.
