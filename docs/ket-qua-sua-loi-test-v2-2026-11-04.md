# Sửa lỗi theo kết quả test v2 — 04/11/2026

Nguồn: `PetHome_ket_qua_test_v2.xlsx`, sheet `Kết quả test`. Đã xử lý 17 mục `Chưa pass`; file Excel gốc được giữ nguyên. Các ghi chú dữ liệu test được dùng để hiểu tình huống, không dùng làm lệnh xóa dữ liệu hiện có.

| STT trong Excel | Nội dung | Kết quả xử lý |
| --- | --- | --- |
| 31 | Tin cứu hộ lọc rỗng | Kiểm tra lại thông báo “Không có kết quả phù hợp.” ở bản đang chạy, cả trình duyệt giả lập và Cloudflare thật. |
| 47 | Kho: lọc và làm mới báo lỗi | Không còn gửi chữ nhập vào tham số UUID. Lọc theo mã mẫu, tên mẫu, mã hàng hoặc mã lô trên danh sách đã tải; Làm mới giữ bộ lọc và không lỗi. |
| 48 | Danh mục: xóa, thứ tự, xuất hiện ngay ở Shop | Có nút Xóa cho quyền quản lý nền tảng. Thứ tự mới lấy số lớn nhất + 1. Danh mục mới được lưu ẩn, có nút Bật/Tắt hiển thị; vẫn chọn được khi tạo sản phẩm. |
| 49 | Sản phẩm: tìm rỗng và form trống | Phân biệt không có kết quả lọc với chưa có danh mục. Form hiện đồng thời các ô thiếu bằng tiếng Việt. |
| 50 | Giỏ hàng chỉ lưu khi rời ô | Tự lưu sau 650ms ngừng gõ; vẫn lưu khi rời ô/Enter. Nháp được lưu ngay theo mã giỏ trong phiên trình duyệt, tải lại ngay sẽ khôi phục và gửi số vừa nhập. |
| 51 | Đăng ký: lỗi còn treo, mật khẩu ngắn, tiếng Anh | Thông báo tiếng Việt cho ô trống, định dạng và độ dài; lỗi xác nhận mật khẩu được xóa khi sửa; kiểm tra lại toàn bộ dữ liệu khi gửi. |
| 52 | Quên mật khẩu: email sai | Hiện thông báo tiếng Việt “Email không đúng định dạng”, không phụ thuộc thông báo mặc định của trình duyệt. |
| 53 | /search: lệch hàng lọc | Dùng lưới đáp ứng, căn đáy các ô; Thương hiệu/Độ tuổi nằm cùng hàng trên desktop, không tràn ngang mobile. |
| 54 | Báo cáo bán hàng chỉ có kho | Thêm tổng đơn, đơn hủy, giá trị đơn không hủy, đơn đã giao, đơn đã thanh toán, giảm giá, thống kê trạng thái và theo ngày. Lọc theo ngày đặt đơn với ranh giới ngày Việt Nam. Phần kho vẫn giữ bên dưới. |
| 60 | Cảnh báo hết/sắp hết mở sai danh sách | Liên kết mở danh sách cảnh báo ngay trên trang kho, bao gồm cả mẫu chưa có lô, hiển thị tên/SKU/số còn/ngưỡng và liên kết lọc các lô. |
| 61 | Bảng không cập nhật sau thao tác | API commit trước khi phản hồi xác nhận/hủy đơn, duyệt/từ chối đánh giá và điều chỉnh kho. Bảng đánh giá cập nhật ngay; khung chỉnh lô lấy bản ghi mới sau tải lại. |
| 62 | Lặp chữ trong hộp xác nhận | Bỏ các cụm “Xác nhận xác nhận”, “hủy đơn đơn này”; dùng tên hành động và câu hỏi có một lần “đơn hàng”. |
| 63 | Nhận nuôi: form trống và dấu phẩy đầu địa chỉ | Form báo đủ ô thiếu bằng tiếng Việt, cuộn tới danh sách lỗi. Địa chỉ chỉ ghép các phần có dữ liệu. |
| 64 | Báo tin/Hỗ trợ: form trống tiếng Anh | Dùng kiểm tra tiếng Việt, liệt kê đầy đủ trường thiếu và xác nhận đồng ý. |
| 65 | Khuyến mãi: thiếu ngày và xóa | Báo rõ thiếu ngày bắt đầu/kết thúc; có nút Xóa cho người quản lý nền tảng. |
| 66 | Sản phẩm: slug, lưu lần đầu, xóa | Slug tự chạy theo toàn bộ tên cho đến khi người dùng sửa thủ công. Nạp lại `updated_at` trước khi trả dữ liệu, sửa lỗi MissingGreenlet lần lưu đầu. Có nút Xóa. |
| 67 | Thiếu nút xóa trong quản trị | Có nút Xóa ở danh mục, sản phẩm, lô, khuyến mãi và đơn hàng; quyền được kiểm tra tại API. |

## Cách hoạt động của nút Xóa

Xóa đưa bản ghi ra khỏi danh sách quản lý và dừng hiển thị/bán/áp dụng khi phù hợp; lưu dấu người thực hiện và giữ lịch sử nghiệp vụ. Không xóa vật lý chứng từ hay làm lệch số liệu đã phát sinh.

- Danh mục: cần chuyển hoặc xóa các sản phẩm trong danh mục trước.
- Sản phẩm: chuyển ẩn và ngừng bán các mẫu; lịch sử đơn và kho vẫn còn.
- Lô: chỉ xóa khi tồn bằng 0 và không có số lượng đang giữ. Điều chỉnh kho phải có lý do và vẫn ghi sổ kho.
- Khuyến mãi: ngừng áp dụng và bỏ khỏi danh sách; lịch sử sử dụng vẫn còn.
- Đơn hàng: chỉ xóa khỏi danh sách đơn đã hủy và chưa thu tiền. Đơn đang xử lý hoặc có thanh toán phải giữ để đối soát.

Chỉ chủ nền tảng hoặc người có `platform_manage` dùng được thao tác này. Tài khoản test đã cấp trước đó vẫn không có quyền quản lý nhân viên/cấp quyền.

## Kiểm tra

- TypeScript và production build Docker thành công.
- 26 trường hợp trình duyệt desktop/mobile đã đạt: 24 trường hợp đạt trong lượt đầy đủ; hai trường hợp form công khai được chạy lại thành công sau khi sửa hạn tin trong fixture. API giả lập tách khỏi dữ liệu thật.
- Kiểm thử backend dùng PostgreSQL mới tạo riêng, chạy migration 0001 → 0016; kiểm tra lưu lần đầu, cập nhật kho, xóa có điều kiện/giữ lịch sử, báo cáo theo ngày Việt Nam và phân quyền. 14 bài ban đầu đạt; bổ sung kiểm tra phân trang và đánh giá riêng.
- Mục 28 “Chưa test”: đã kiểm tra thành viên thường mở `/admin` bằng bộ test trình duyệt.
- Mục 55 “Chưa test”: kiểm tra backend với 13 tin giả có cùng thời gian tạo, trang 1 có 12 tin, trang 2 có 1 tin, không lặp/mất tin; cursor sai trả 422. Không thêm 13 tin này vào dữ liệu thật.
- Kiểm tra trực tiếp trên Cloudflare bằng tài khoản test: các API kho/sản phẩm/danh mục/báo cáo trả 200; API nhân viên trả 403; lọc rỗng tin cứu hộ/kho/sản phẩm, slug, thông báo ngày khuyến mãi, báo cáo, nút Xóa và căn hàng tìm kiếm đều đạt. Không gửi tạo sản phẩm/đơn hay xóa bản ghi thật trong lượt kiểm tra này.

## Bản đang chạy

Đã sao lưu database và ảnh trước cập nhật tại `.local-backups/pethome-20261104-105738-1340fc9f/`, sau đó chạy migration `0016` và khởi động lại các dịch vụ bằng image mới.

Link giữ nguyên: https://groundwater-recording-ips-following.trycloudflare.com/

Dùng lại tài khoản test đã cấp. Nếu trình duyệt đang mở giao diện cũ, tải lại toàn bộ trang để nhận bản mới. Các bản ghi test được liệt kê cuối Excel chưa được tự động xóa.
