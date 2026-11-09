# Đối chiếu sửa lỗi PetHome — 04/11/2026

Nguồn: `PetHome_ket_qua_test.xlsx`, sheet `Kết quả test`, 15 dòng có trạng thái `Chưa pass`. STT bên dưới là cột A trong file gốc. File gốc được giữ nguyên. “Đã sửa” là đã thay đổi mã local và kiểm tra trong phạm vi ghi dưới đây, chưa phải kết quả nghiệm thu trên bản triển khai.

| STT | Trường hợp | Thay đổi và trạng thái |
| --- | --- | --- |
| 1 | Google đăng nhập | **Chờ cấu hình ngoài mã nguồn.** `origin_mismatch` cần thêm đúng origin đang test vào Authorized JavaScript origins của OAuth Web client trùng `GOOGLE_CLIENT_ID`. Xem `docs/dang-nhap-google.md`. Chưa đăng nhập Google thật để nghiệm thu. |
| 2 | Đăng nhập để trống | Đã sửa: hiện thông báo tiếng Việt thiếu tên tài khoản hoặc mật khẩu. Đã kiểm tra trình duyệt. |
| 11 | Tin của tôi khi chưa đăng nhập | Đã sửa: lỗi đăng nhập/tải dữ liệu không còn hiện kèm “Bạn chưa đăng tin nào”. Đã kiểm tra trình duyệt. |
| 14 | Địa chỉ nhập sai SĐT | Đã sửa: thông báo nêu rõ SĐT người nhận; backend kiểm tra cả tạo và sửa; API lỗi xác thực các ô địa chỉ được dịch sang tên ô. Đã kiểm tra trình duyệt và backend. |
| 15 | Sửa địa chỉ | Đã thêm Sửa, Lưu thay đổi, Hủy sửa; giữ mã tỉnh/huyện/xã của bản ghi đang sửa. Đã kiểm tra sửa và tải lại trình duyệt. |
| 17 | Shop cuộn ngang | Đã bỏ bố cục `100vw` lệch theo thanh cuộn và lề âm ở thẻ sản phẩm. Đã kiểm tra chiều rộng desktop 1440px và mobile 390px. |
| 19 | Shop còn 90, chi tiết còn 47 | Đây là tổng các loại so với loại đang chọn. Đã ghi rõ “Tổng còn 90 (2 loại)” ở danh sách, tên loại cạnh số còn ở chi tiết. Kiểm tra tổng bằng dữ liệu giả lập 47 + 43; cần xác nhận lại sản phẩm thật sau triển khai. |
| 21 | Nhập số lượng giỏ hàng | Đã sửa: lưu nháp trong ô; chỉ gửi khi rời ô hoặc Enter; kiểm tra số nguyên 1–99; giữ số cũ và báo lỗi khi vượt tồn kho. Đã kiểm tra gõ chậm `12`, `25`, `0`, vượt tồn kho, tải lại và xóa. |
| 22 | Số trên giỏ hàng không nhất quán | Đã sửa: mọi phản hồi giỏ hàng phát sự kiện cập nhật header bằng `item_count` (tổng số lượng). Đã kiểm tra đổi 12/25, tải lại và xóa. |
| 25 | Tra cứu để trống, cuộn ngang | Đã sửa thông báo thiếu mã đơn/SĐT và bố cục rộng hơn màn hình. Đã kiểm tra trình duyệt desktop/mobile. |
| 26 | Tải tin có lúc quá 20 giây | **Đã tối ưu, chưa xác nhận hết lỗi trên hệ thống thật.** Gọi đồng thời dữ liệu trang cứu hộ, thêm trạng thái đang tải; gom đọc tác giả của 50 tin thành một truy vấn thay vì đọc từng người; trì hoãn lọc 300ms khi gõ. Test backend xác nhận đọc tác giả theo lô. Cần đo lại trên bản triển khai qua Cloudflare, đồng thời so sánh trực tiếp API để xác định phần chậm còn lại. |
| 28 | Thành viên mở /admin | Đã sửa cả layout máy chủ và AdminShell: hiện không có quyền, không chuyển thành viên đang đăng nhập về form login. Đã kiểm tra desktop/mobile; bảo vệ quyền backend được giữ nguyên. |
| 31 | Quản trị lọc tin ra rỗng | Đã thêm “Không có kết quả phù hợp.”, loại phản hồi tìm kiếm cũ tới muộn. Đã kiểm tra trình duyệt. |
| 32 | Từ chối xong còn Chờ duyệt | Đã dùng bản ghi trả về để cập nhật ngay, loại yêu cầu đọc cũ tới muộn rồi tải lại bộ lọc hiện tại. Đã kiểm tra từ chối mà không tải lại trang. |
| 35 | Hai trang báo lệch kho khác nhau | Đã dùng chung truy vấn đối chiếu tồn kho thực; bỏ dòng `order_release` cũ vì chỉ nhả giữ hàng, không tăng tồn thực. Kiểm tra backend: lô có nhập 15, xuất 5, nhả giữ 5 không bị báo sai; lô thực sự lệch -2 vẫn bị phát hiện, cả hai API cùng báo một lô lệch. Không chỉnh dữ liệu kho thật. |

## Kiểm tra đã chạy

- Frontend: `tsc --noEmit --incremental false` thành công.
- Playwright: 14/14 bài, gồm 7 luồng trên desktop và mobile, qua Next.js local thật với API giả lập độc lập, không ghi dữ liệu vào hệ thống thật. Bộ test: `qa-e2e/tests/07-test-report-regressions.spec.ts`; chạy từ `qa-e2e` bằng `npx playwright test --config regression.config.ts`.
- Backend: 7/7 bài tại `backend/tests/test_report_regressions.py`. Dùng SQLite trong bộ nhớ cho phép cộng tồn và mock cho truy vấn danh sách; không thay thế kiểm tra tích hợp trên PostgreSQL thật.
- Hai trường hợp “Chưa test” trong Excel (quản lý sản phẩm/danh mục và mobile tổng thể) không được tự đổi thành Pass. Kiểm tra mobile trong đợt này chỉ bao phủ các luồng sửa phía trên.

## Sau khi triển khai

Chạy lại 15 trường hợp trên cùng hostname đã báo lỗi. Riêng Google cần chủ dự án OAuth lưu origin chính xác trên Google Cloud; máy local hiện đặt `APP_PUBLIC_URL=http://localhost`, không cho biết hostname Cloudflare từng dùng để test. Riêng tải trang cần đo lại ở môi trường thật. Docker chưa chạy trong phiên sửa này, nên chưa nghiệm thu toàn bộ ứng dụng với cơ sở dữ liệu thật và chưa triển khai bản sửa.

Nguồn cấu hình Google: https://developers.google.com/identity/gsi/web/guides/get-google-api-clientid
