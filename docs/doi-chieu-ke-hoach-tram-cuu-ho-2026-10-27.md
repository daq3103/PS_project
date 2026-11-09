# Đối chiếu kế hoạch Trạm cứu hộ — cập nhật 0012

Phạm vi người dùng đã chốt: **hoàn thiện P0 và P1 cho một trạm Hà Nội**, chưa mở P2 nhiều trạm/tài trợ định kỳ/tìm bằng ảnh. Nguồn: `D:/Download/ke_hoach_he_thong_tram_cuu_ho.docx`.

Hướng dẫn và giới hạn hiện hành nằm tại [Vận hành Trạm cứu hộ](van-hanh-tram-cuu-ho.md). Phần ghi chép 0011 phía dưới là lịch sử đợt đầu, không phải danh sách chức năng còn thiếu hiện tại.

## Bổ sung trong 0012

- Lịch hẹn có xác nhận, đổi/hủy, khung gặp tự chọn và khóa chống đặt trùng. Lịch theo giờ Việt Nam, lưu UTC.
- Xác minh liên hệ thực tế, đồng ý sử dụng hồ sơ, biên bản và xác nhận bàn giao trước khi hoàn tất nhận nuôi.
- Hồ sơ người đồng hành/foster/vận chuyển, duyệt năng lực, ca trực có người dự phòng, bàn giao ca, đề nghị đổi lịch rảnh và nhật ký đúng nhà tạm.
- Lịch chăm sóc lặp, nhắc việc/quá hạn/tin chưa nhận qua thông báo trong tài khoản; chống tạo lặp sau rollback/replay. Chuyển người/nơi và kết thúc đợt dừng công việc/lịch cũ.
- Hộp thư riêng theo hồ sơ và hộp thư hỗ trợ trạm, kiểm tra chủ hồ sơ và quyền điều phối; tách khỏi CSKH Shop.
- Ảnh bé độc lập, bản chụp riêng tư, liên kết tải có hạn và kiểm tra quyền khi tải; video ngoài, mốc công khai riêng, theo dõi bé và lựa chọn nhận cập nhật.
- Bộ lọc hồ sơ bé theo tên/màu/giống/khu vực, tuổi, kích thước và khả năng nhận nuôi.
- Nhu cầu/cam kết/vận chuyển/thực nhận hiện vật, lô dùng/cách ly/giải phóng/loại bỏ, kiểm tra hạn và chống vượt lượng còn lại. Gắn đơn Shop mua tặng; không cộng tiền hiện vật vào quỹ.
- Chiến dịch theo quỹ hoặc bé, mục tiêu/thời gian/chính sách; chuyển khoản theo mã riêng, đối soát thủ công hoặc thông báo HMAC từ bộ nối tin cậy, xử lý ngoại lệ, tiền muộn và đề nghị hoàn có người khác duyệt.
- Báo cáo hoạt động theo kỳ, nguồn/mẫu số, nhóm theo dõi quay lại 30 ngày, CSV tổng hợp; lịch sử thay đổi chỉ chủ tài khoản; danh sách ngoại lệ phục hồi.
- Phiên bản báo cáo quỹ, chứng từ công khai đã được người vận hành che thông tin và chủ trạm duyệt; không lộ người đóng góp.
- Cấu hình staging riêng, backup DB + ảnh + checksum có giới hạn dung lượng, bản sidecar tùy chọn chạy theo chu kỳ và cờ tạm dừng tự động khi phục hồi.

## Nghiệm thu và phần phụ thuộc vận hành

Đã chạy Docker và migration `0012 (head)`. Kết quả đợt này: **63 kiểm thử backend đạt** trên PostgreSQL tạm, container thử giới hạn 384 MB; lint đạt; frontend production build đạt với trần 640 MB/một CPU và ngưỡng tự dừng của máy. Browser smoke chạy trên image Linux cuối với dữ liệu giả: desktop/mobile, liên hệ, báo tin, hộp thư riêng, foster, nhật ký, ca trực, giờ Việt Nam, sổ quỹ, tải CSV và nhật ký thay đổi. Ảnh tại `PetHome-screenshots/rescue-*.png`.

Sao lưu trước nâng cấp gồm DB và volume ảnh tại `.local-backups/pethome-20261027-153255-be4511ae`, có manifest SHA256. Đã khôi phục DB vào database tạm và ảnh vào volume tạm riêng; chạy 0011 → 0012, so khớp dữ liệu tài khoản/quyền, đơn hàng, kho, bài đăng và các bảng trạm cũ. Các môi trường tạm đã dọn. Bản thật giữ nguyên 16 tài khoản, 15 đơn và dữ liệu kho/bài đăng đã có; không tự cấp thêm quyền.

Smoke trên website thật xác nhận các trang mới và `/readyz` trả 200, quản trị chuyển khách tới đăng nhập, API quản trị trả 401, tạo khoản hỗ trợ vẫn trả 503 khi chưa bật. Log truy cập Nginx bỏ query/token, SQL không ghi giá trị tham số vào lỗi; đã kiểm tra query thử không xuất hiện trong access log. Không chạy thử tải đông người hoặc mở thêm môi trường staging trên máy ít RAM.

| Kịch bản | Phần mềm / kiểm chứng |
|---|---|
| R01 | Tin, ca, danh tính bé và lượt tiếp nhận tách riêng; kiểm thử báo cáo trên dữ liệu có nhiều bé, nhiều tin và một bé quay lại |
| R02–R05 | Giữ ID khi quay lại; tranh chỗ cuối; hai người duyệt đồng thời qua HTTP chỉ một người thắng; chặn khi xác minh chủ |
| R06–R07 | Đổi/hủy lịch không nhắc phiên cũ; chuyển nơi/người dừng lịch cũ; có nhắc tin chưa nhận và người dự phòng; chưa quảng cáo trực 24/7 |
| R08–R10 | Thông báo lặp sau đối soát tay không cộng lại; kiểm tra chữ ký/binding/số tiền; tiền muộn giữ đúng quỹ và vào ngoại lệ. Kiểm thử dữ liệu giả, chưa tích hợp ngân hàng thật |
| R11–R13 | Giữ hạn mức chi/hoàn, khác người duyệt, chống ghi lại; public không trả tên người đóng góp; chỉ hiện vật thực nhận cộng tồn một lần |
| R14 | Quà từ đơn Shop là hiện vật riêng; không tự trích tiền Shop. Đơn thay đổi sau khi nhận quà tạo tình huống cần đối chiếu, không tự đảo hàng thực nhận |
| R15–R16 | Kiểm tra quyền ở API/file/hộp thư; backend kiểm tra lại trạng thái nhận nuôi, không tin nút public cũ |
| R17 | Có khóa nguồn/replay và cờ dừng tự động, công cụ backup/restore thử. Đối chiếu tiền/bàn giao/thực nhận sau khôi phục cần con người xác nhận |
| R18 | Báo cáo tách foster, trải nghiệm, nhận nuôi, quay lại; có kỳ chốt, nguồn và mẫu số. Không chia tùy tiện hai tổng tháng |

**Chưa bật nhận tiền thật.** Thiếu người/tài khoản nhận và xác nhận chính sách; link liên hệ vẫn là link mẫu theo yêu cầu. Chưa có đích backup ngoài máy, tên miền/email và lịch trực thật. Đây là cấu hình/nghiệm thu thực tế phải do chủ trạm cung cấp, không thể điền giả để đánh dấu hoàn tất. Chưa cam kết RPO/RTO hoặc sức tải khi chưa đo.

Các tài liệu gửi lên nhận bằng ảnh/bản chụp JPEG/PNG/WebP; không có nhận PDF/Word. Chứng từ cần được che thông tin trước khi duyệt; không có cơ chế AI tự bảo đảm che hết thông tin riêng. Thông báo và hộp thư có nút tải lại, không hứa phản hồi tức thời.

---

## Lịch sử đợt 0011 (giữ để truy vết)

# Đối chiếu và vận hành Trạm cứu hộ PetHome

Nguồn yêu cầu: `D:/Download/ke_hoach_he_thong_tram_cuu_ho.docx`. Nội dung trích để đối chiếu: `docs/ke-hoach-tram-cuu-ho-nguon.txt`. Đây là đợt triển khai nền nghiệp vụ; chưa đánh dấu hoàn tất toàn bộ P0, P1 hoặc P2 của tài liệu.

Theo xác nhận của chủ dự án, khu vực là Hà Nội. Hồ sơ các bé luôn xem được; chưa có lịch trực cam kết, không quảng cáo phản hồi hoặc điều phối cứu hộ 24/7. Liên hệ qua Zalo/Facebook hoặc gửi yêu cầu tới quản trị viên.

## Các màn hình

| Địa chỉ | Chức năng |
|---|---|
| `/tram-cuu-ho` | Cộng đồng tìm chủ, mất/nhặt và điều hướng vào hoạt động trạm |
| `/tram-cuu-ho/cac-be` | Danh sách hồ sơ đã được duyệt công bố, lọc loài và phân trang |
| `/tram-cuu-ho/be/[slug]` | Câu chuyện đã duyệt, trạng thái thực tế, liên hệ Zalo/Facebook; chỉ mở đăng ký nhận nuôi khi đủ điều kiện |
| `/tram-cuu-ho/bao-tin` | Báo tin cần hỗ trợ, đồng ý sử dụng thông tin liên hệ, theo dõi tin của tài khoản/thiết bị |
| `/tram-cuu-ho/dong-hanh` | Hướng dẫn liên hệ chăm sóc tạm, vận chuyển và hiện vật |
| `/tram-cuu-ho/minh-bach` | Báo cáo quỹ được chủ trạm duyệt công bố, có thời điểm chốt |
| `/admin/rescue` | Hồ sơ bé, đợt chăm sóc, nhật ký, công việc, tin báo, ca cứu hộ, nơi chăm sóc, hiện vật |
| `/admin/rescue/finance` | Sổ quỹ nội bộ, chứng từ thu/đối soát/hoàn/phí, đề nghị chi và duyệt chi |

## Cấu hình và phân quyền

- Sửa khu vực/nội dung hỗ trợ tại `frontend/src/config/rescue.ts`; cấu hình tương ứng của API nằm ở endpoint `rescue/config` trong `backend/app/modules/rescue/router.py`.
- Sửa URL liên hệ tại `frontend/src/config/social-links.ts`, rồi build lại frontend. Hiện dùng URL mẫu theo yêu cầu trước đó, chưa phải trang chính thức của trạm.
- Chủ tài khoản vào **Nhân viên** để cấp một hoặc nhiều quyền: **Điều phối trạm** (`rescue_manage`), **Chăm sóc được giao** (`rescue_care`), **Sổ quỹ trạm** (`rescue_finance`). Quyền kho và CSKH Shop được giữ riêng.
- Migration không tự nâng quyền người dùng hiện có. Nhân viên chỉ có quyền CSKH Shop sẽ không còn tự có quyền duyệt bài cứu hộ; chủ tài khoản cần cấp thêm quyền điều phối nếu phù hợp.
- Người chăm sóc chỉ xem bé/công việc được giao và tin báo được phân công. Chủ tài khoản có đủ quyền. MFA của chủ tài khoản vẫn giữ theo phiên như quyết định trước.

## Nghiệp vụ đã bổ sung

- ID bé ổn định, nhiều đợt tiếp nhận riêng; quay lại trạm giữ nguyên ID và lịch sử. Một bé chỉ có một đợt đang mở, có ràng buộc PostgreSQL.
- Nơi chăm sóc có sức chứa, loài và thời gian sẵn sàng; khóa khi phân chỗ. Chuyển nhà chăm sóc tạm không tự ghi thành nhận nuôi. Có xác nhận bàn giao và người chịu trách nhiệm mới.
- Nhật ký nối tiếp; bản sửa tham chiếu bản cũ. Công việc có người phụ trách, hạn và trạng thái; kết thúc/chuyển đợt dừng công việc cũ.
- Tin báo riêng tư, giới hạn tần suất, chống gửi trùng, phân công và xác nhận tiếp nhận. Một ca có thể nối nhiều tin và nhiều bé.
- Hồ sơ công khai dùng bản đã duyệt riêng với bản nháp; lưu lịch sử phiên bản công bố. Không công khai địa chỉ nội bộ, liên hệ người báo hoặc nhật ký chăm sóc riêng.
- Liên kết luồng nhận nuôi hiện có với hồ sơ bé. Xác minh chủ chặn ghép/bàn giao; hoàn tất bàn giao kết thúc đợt và tạo công việc hỏi thăm sau 3, 14, 30 ngày. Khi bé quay lại, có thể liên kết tin nhận nuôi mới mà giữ lịch sử tin cũ.
- Sổ quỹ tách tiền Shop, số đã xác nhận và số thực đối soát; khoản chi được duyệt giữ ngân sách. Người đề nghị không tự duyệt chi. Mã chứng từ duy nhất, gửi lại không ghi chi hai lần. Ghi hoàn/đối soát phải tham chiếu khoản thu và không vượt số cho phép. Thao tác sổ quỹ chỉ ghi chứng từ thực tế, không tự chuyển tiền ngân hàng.
- Hiện vật chỉ ghi lượng thực nhận/đã kiểm tra, chống ghi trùng theo chứng từ; không cộng tiền quỹ. Đây là sổ nhận, chưa là hệ thống xuất/nhập/tồn hiện vật đầy đủ.
- Tiền đóng góp trực tuyến vẫn tắt. API tạo ý định đóng góp trả thông báo chưa mở; không dùng kênh thanh toán Shop cho trạm. Báo cáo công khai chỉ chứa tổng đã duyệt, không trả tên hoặc thông tin người đóng góp.

## Đối chiếu nghiệm thu trong tài liệu

| Mã | Đã có và giới hạn |
|---|---|
| R01 | Có ca, nhiều tin và nhiều ID bé. Chưa có dashboard thống kê ca để nghiệm thu mẫu số |
| R02 | Đã kiểm thử hai đợt trên cùng ID, không mất lịch sử |
| R03 | Đã kiểm thử hai yêu cầu đồng thời giành chỗ cuối: chỉ một thành công |
| R04 | Kế thừa khóa bài nhận nuôi và một lựa chọn độc quyền; luồng liên kết đã kiểm thử. Cần thêm ca hai người duyệt đồng thời qua HTTP |
| R05 | Đã kiểm thử giữ xác minh chủ chặn duyệt/bàn giao |
| R06 | Chuyển nơi chăm sóc cập nhật trách nhiệm và dừng việc cũ. Chưa có module lịch hẹn/nhắc lịch |
| R07 | Thông báo rõ chờ xác nhận, có kênh liên hệ và danh sách chưa nhận. Chưa có lịch trực, leo thang ngoài giờ tự động |
| R08–R10 | Có sổ thủ công và chống dùng trùng mã chứng từ với Shop. Chưa mở cổng đóng góp, callback hoặc tự xử lý phần dư chiến dịch |
| R11 | Đã kiểm thử giữ ngân sách, không tự duyệt, không hoàn vượt tiền khả dụng và ghi chi lại không tăng chi. Chưa có adapter thực hiện hoàn tiền thật |
| R12 | Public chỉ trả báo cáo tổng đã duyệt; không trả thông tin người đóng góp, kể cả khi người đó không chọn ẩn danh |
| R13 | Có biên nhận hiện vật duy nhất theo lượng thực nhận. Chưa có vận đơn/callback giao hiện vật |
| R14 | Chưa có luồng trích hỗ trợ từ đơn Shop; hai bên vẫn tách biệt |
| R15 | Đã kiểm thử nhân viên Shop, người chăm sóc khác phạm vi và người sổ quỹ không có quyền điều phối bị chặn tại API |
| R16 | Public đọc trạng thái thực; backend kiểm tra điều kiện nhận nuôi dưới khóa. Đã kiểm thử bàn giao gửi lại không tạo thêm việc |
| R17 | Đã sao lưu và khôi phục thử trước migration, so khớp dữ liệu cũ. Chưa diễn tập toàn bộ sự cố worker/khôi phục tiền và bàn giao thực tế |
| R18 | Có dữ liệu loại kết quả và đợt riêng. Chưa có báo cáo nghiệp vụ với kỳ chốt/mẫu số/xuất dữ liệu |

## Phần cần triển khai tiếp

1. Lịch gặp/gọi điện/bàn giao có xác nhận, đổi/hủy lịch và tác vụ nhắc bền vững; nhắc quá hạn/chưa ai nhận và người dự phòng.
2. Hồ sơ người nhận nuôi có xác minh liên hệ, sự đồng ý, bản bàn giao và tiêu chí được trạm duyệt; file/ảnh riêng tư có quyền truy cập và chính sách lưu giữ.
3. Đăng ký foster/tình nguyện từ người dùng, hồ sơ duyệt, ca trực; dữ liệu năng lực foster chi tiết hơn. Hiện quản trị viên nhập nơi chăm sóc, còn người dùng liên hệ trực tiếp.
4. Quản lý ảnh riêng cho hồ sơ trạm, quyền công bố và video. Hiện ảnh public lấy từ tin nhận nuôi được duyệt có liên kết; không tự công bố ảnh báo tin riêng.
5. Tài khoản nhận tiền, chủ thể nhận, chính sách phần dư/hoàn và người đối soát được xác nhận, rồi mới triển khai cổng đóng góp, webhook, giao dịch muộn và đối soát định kỳ. Không bật bằng cách chỉ sửa cờ frontend.
6. Tồn hiện vật, nhu cầu, sử dụng/cách ly/hết hạn; vận chuyển và quà từ Shop có chứng từ tách biệt. Chưa trích quỹ từ đơn Shop.
7. Dashboard hoạt động trạm theo kỳ chốt, mẫu số và xuất dữ liệu theo quyền; kiểm thử đồng thời qua HTTP cho nhận nuôi và các tình huống lỗi dịch vụ.
8. Lịch trực/đầu mối thật, nghiệm thu quy trình ngoài đời, backup ngoài máy, staging và diễn tập phục hồi. Chưa cam kết sức tải hoặc RPO/RTO chỉ dựa trên lượt build/test.

## Kiểm chứng đợt này

- 49 kiểm thử backend qua trên PostgreSQL thật trong database tạm tự tạo/xóa; gồm trạm, cộng đồng, phân quyền, phiên MFA, Shop, catalog, mật khẩu và analytics. Giới hạn container 256 MB; không OOM.
- Browser smoke với dữ liệu giả: hồ sơ công khai, Zalo/Facebook, gửi báo tin, nhật ký, foster, sổ quỹ, desktop 1280 px và mobile 390 px. Không ghi vào database thật.
- Ảnh nằm trong `PetHome-screenshots/rescue-*.png`.
- Sao lưu trước nâng cấp: `.local-backups/pethome-before-rescue-0011.dump`. Đã restore vào database tạm, chạy 0010 → 0011 và so khớp tài khoản, đơn, dòng hàng, lô, giữ hàng, bài đăng.
- Build Docker frontend giới hạn 768 MB, một CPU; không chạy thử tải đông người.
- Đã chạy bản Docker mới và migration `0011 (head)`. Smoke trên địa chỉ local xác nhận trang chủ, Shop, các trang trạm, API public và `/readyz` trả 200; quản trị chuyển khách sang đăng nhập, API quản trị trả 401. Không mở lại tunnel public trong đợt này.
