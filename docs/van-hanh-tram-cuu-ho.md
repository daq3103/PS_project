# Vận hành một trạm Hà Nội — bản P0/P1

Phạm vi đã chốt: một trạm tại Hà Nội; P2 (nhiều trạm độc lập, tài trợ định kỳ, tìm thú lạc bằng ảnh và gợi ý ghép bằng AI) nằm ngoài đợt này. Hồ sơ xem được mọi lúc, không đồng nghĩa trạm có người trực 24/7.

## Các bước sử dụng

1. Chủ tài khoản cấp riêng quyền điều phối, chăm sóc hoặc tài chính ở **Nhân viên & quyền**. Duyệt hồ sơ tình nguyện/foster không tự cấp quyền nhân viên. Nhân viên chăm sóc cần vừa có quyền vừa được giao việc; tài chính không tự có quyền xem hồ sơ nhận nuôi. Chủ tài khoản vẫn xác minh hai bước lúc đăng nhập và giữ trong phiên.
2. Vào **Chăm sóc & tiếp nhận** tạo bé, đợt tiếp nhận, nơi chăm sóc và người chịu trách nhiệm. Bé quay lại phải chọn ID cũ và mở đợt mới. Chuyển nhà tạm không phải nhận nuôi. Đổi người tại cùng nơi dùng **Bàn giao người chịu trách nhiệm tại chỗ**; cần xác nhận thực tế và xem lại lịch chăm sóc.
3. Vào **Lịch & điều phối trạm** cập nhật mô tả nhận dạng, video, quan sát có ngày và ảnh. Duyệt lại hồ sơ ở bàn chăm sóc để cập nhật bản công khai. Mốc hành trình công khai được nhập riêng; nhật ký riêng không tự chuyển ra ngoài. Ảnh riêng phải được kiểm tra quyền và nội dung trước khi công bố.
4. Người xem đăng ký nhận nuôi, đồng ý sử dụng hồ sơ và trao đổi trong **Đồng hành của tôi**. Điều phối ghi xác minh liên hệ thực tế, điều kiện/biên bản; sau đó xét duyệt. Khi bàn giao phải ghi xác nhận người nhận đã đồng ý và đã nhận bé, rồi hoàn tất ở màn hình hồ sơ nhận nuôi. Hệ thống chặn duyệt/bàn giao khi chưa đủ căn cứ hoặc đang xác minh chủ; chỉ một gia đình được duyệt cho mỗi bé.
5. Điều phối nhập lịch hoặc mở khung gặp; người có hồ sơ tương ứng chọn khung còn trống và xác nhận lịch. Khung giờ được kiểm tra lại khi đặt, không lấy danh sách đang hiển thị làm bằng chứng còn chỗ. Giờ biểu mẫu và hiển thị dùng Việt Nam; lưu dữ liệu UTC. Đổi/hủy lịch làm thay phiên bản và không dùng lần nhắc cũ.
6. Người dân đăng ký foster/tình nguyện/vận chuyển qua **Đồng hành của tôi**. Điều phối duyệt điều kiện và sức chứa trước khi gán bé. Nhà tạm có thể đề nghị đổi lịch rảnh, ghi nhật ký cho đúng bé đang ở nhà mình; thay đổi năng lực không có hiệu lực trước duyệt. Không cho rút nhà tạm khi vẫn còn bé chưa được bàn giao.
7. Tạo lịch chăm sóc lặp theo hướng dẫn đã được người chịu trách nhiệm duyệt. Worker tạo từng lần việc theo khóa nguồn, nhắc trong tài khoản và báo quá hạn cho điều phối. Khi chuyển nơi/người hoặc đóng đợt, dừng lịch và việc cũ; lịch mới cần được xem xét lại. Không tự chẩn đoán hay kê điều trị.
8. Người dùng có thể trao đổi riêng trong từng hồ sơ hoặc gửi lời nhắn chung cho trạm. Chỉ người có quyền xử lý và chủ hồ sơ được xem. Đây là hộp thư có nút tải lời nhắn mới, không phải cam kết chat trực tuyến tức thời. Zalo/Facebook là kênh ngoài; thay URL mẫu ở `frontend/src/config/social-links.ts`.

## Hiện vật và Shop

Điều phối công bố nhu cầu. Người hỗ trợ đăng ký lượng dự kiến, có thể gắn đơn Shop thuộc tài khoản của mình và cập nhật vận đơn. Chỉ khi kiểm tra thực tế, người của trạm mới ghi số đã nhận và số đủ điều kiện dùng. Một vận đơn/biên nhận không tạo hai lô; không cộng giá trị hiện vật vào tiền quỹ.

Đơn Shop gắn quà phải giao và thanh toán hoàn tất trước khi trạm xác nhận nhận quà từ đơn đó. Việc mua hàng vẫn là giao dịch Shop riêng, không tự cộng khoản hỗ trợ hay tạo ưu tiên nhận nuôi. Địa chỉ giao thật phải được trao đổi với trạm; hệ thống không bịa địa chỉ nhà tạm.

Kho trạm có sử dụng, cách ly, trả lại dùng được và loại bỏ từ phần cách ly. Hàng hết hạn không được xuất dùng/giải phóng về dùng được. Không tự sửa số lượng biên nhận để đảo lịch sử. Nếu đơn Shop hoàn sau khi hàng đã tặng, kiểm tra danh sách ngoại lệ và hàng thực tế; không tự đảo tồn trạm hoặc ghi thêm khoản tiền giả.

## Đóng góp và đối soát

**Mặc định vẫn tắt nhận khoản mới.** Bản này hỗ trợ chuyển khoản theo mã riêng và nhân viên kiểm tra chứng từ. Không phải tích hợp sẵn API của mọi ngân hàng, và không tự chuyển tiền hoàn. Chưa có thông tin người nhận thật nên không mở nhận tiền trên máy người dùng.

Cấu hình backend trong `.env`, độc lập với khóa payOS của Shop:

```dotenv
RESCUE_DONATIONS_ENABLED=false
RESCUE_FUND_POLICY_CONFIRMED=false
RESCUE_RECIPIENT_NAME=
RESCUE_BANK_NAME=
RESCUE_BANK_ACCOUNT=
RESCUE_MERCHANT_ID=
RESCUE_WEBHOOK_SECRET=
RESCUE_AUTOMATION_PAUSED=false
```

Chủ trạm xác nhận chủ thể/tài khoản nhận, mục đích quỹ, cách xử lý dư/thiếu/hoàn và người đối soát; điền cấu hình rồi mới bật hai cờ đầu và chạy lại API. Tạo quỹ có chính sách, chuẩn bị chiến dịch và chủ trạm duyệt mở. Cờ frontend không thể mở nhận tiền. Dừng khoản mới vẫn giữ đường đối soát giao dịch đã phát sinh.

Mỗi khoản hỗ trợ lưu mục đích và người nhận ở thời điểm tạo; chỉ xác nhận sau đối soát tiền thực nhận. Sổ tách số xác nhận, thực đối soát, hoàn, phí, chi và các khoản đã giữ ngân sách. Chi và hoàn phải có người khác duyệt; ghi chứng từ chuyển tiền thực tế không đồng nghĩa website tự chuyển tiền ngân hàng.

Thông báo sai số tiền/đơn vị nhận, không khớp mã, đã có trong Shop hoặc tiền đến muộn đi vào ngoại lệ. Người có quyền tài chính kiểm tra chứng từ rồi ghép lại, tạm giữ đúng mục đích theo chính sách, hoặc lập đề nghị hoàn. Lưu dấu vết sửa và không ghi tiền lại khi thông báo bị gửi nhiều lần. Khoản thu ngoài hệ thống có thể ghi thủ công theo chứng từ duy nhất; không dùng lại mã ngân hàng đã thuộc tiền hàng Shop.

### Giao thức nhận thông báo cho bộ nối đối soát riêng

Đường vào `POST /api/v1/webhooks/rescue/transfers` dành cho một bộ nối tin cậy do đơn vị vận hành cấu hình. Nó **không tự kết nối hoặc đọc tài khoản ngân hàng**. Không công bố secret, không dùng secret của Shop. Cần khóa ngẫu nhiên ít nhất 32 ký tự.

Body JSON có `code` (mã hỗ trợ), `amount` (VND nguyên), `reference` (mã giao dịch duy nhất), `merchant` (mã đơn vị nhận khớp snapshot), `note` (căn cứ). Header `X-Rescue-Signature` là HMAC-SHA256 dạng hex trên đúng byte body bằng `RESCUE_WEBHOOK_SECRET`. Bộ nối phải xác minh tiền thực nhận ở nguồn trước khi ký. Không ký payload chỉ do người chuyển tiền gửi lên.

API xác minh chữ ký, mã, số tiền, binding và chống lặp. Thông báo cũ vẫn được nhận khi tạm dừng chiến dịch; trường hợp không khớp được lưu để đối soát, không tự ghi khoản đóng góp. Kiểm thử trong dự án dùng dữ liệu giả và chữ ký thử; chưa kiểm chứng bộ nối/ngân hàng thật.

## Công bố, ảnh và lưu giữ

API công khai trả tập trường đã duyệt, không trả người báo, nơi nhà tạm, hồ sơ gia đình hoặc tên người đóng góp. Cập nhật nội dung nội bộ không làm thay bản đã công bố trước khi duyệt lại. Người theo dõi lựa chọn nhận thông báo riêng, không bị thêm vào marketing Shop.

Ảnh/bản chụp giới hạn 5 MB, JPEG/PNG/WebP; kiểm tra ảnh và tạo lại pixel để bỏ EXIF. Giấy tờ được nhận bằng bản chụp, **chưa hỗ trợ PDF/Word tải lên**. Tệp riêng cần phiên hợp lệ, quyền trên hồ sơ và liên kết hết hạn sau 5 phút. Quyền được kiểm tra lại khi tải, không dựa vào URL khó đoán.

Bản chụp trong khu chăm sóc dùng loại tài liệu riêng, không có đường công bố công khai kể cả người điều phối bấm công bố. Ảnh dùng cho câu chuyện được nhập ở phần ảnh hồ sơ bé riêng. Khi gỡ hồ sơ, API công khai không còn trả hồ sơ đó. Nhật ký truy cập chỉ giữ đường dẫn/trạng thái/thời gian, không ghi query chứa mã tải tệp; lỗi SQL che tham số.

Chứng từ quỹ chỉ công khai bản đã được người vận hành che thông tin rồi chủ trạm duyệt cùng báo cáo. Website không tự nhận diện và che tên/số tài khoản bằng AI. Gỡ chứng từ quỹ khỏi công khai vẫn giữ bản riêng để đối soát; ảnh hồ sơ thông thường được đánh dấu gỡ ngay, xóa byte sau 7 ngày. Chính sách lưu hồ sơ/giấy tờ vận hành dài hạn cần chủ trạm chốt trước dữ liệu thật. Không tùy tiện xóa sổ quỹ hoặc lịch sử bàn giao để xử lý yêu cầu truyền thông.

## Báo cáo và phục hồi

**Báo cáo hoạt động trạm** chọn kỳ tối đa một năm, có giờ chốt và nguồn chỉ số. Tin/ca/danh tính bé/lượt vào được đếm riêng; kết quả nhận nuôi, về chủ, chuyển đơn vị, qua đời và kết quả khác tách nhau. Nhà tạm và buổi trải nghiệm không tính thành nhận nuôi. Tỷ lệ quay lại lấy nhóm bàn giao trong kỳ và cửa sổ 30 ngày; API trả số nhóm đã đủ thời gian theo dõi. Có tải CSV tổng hợp, không xuất thông tin riêng của gia đình.

**Minh bạch** chỉ trả báo cáo tài chính đã duyệt, các lần chốt cũ và ảnh chứng từ đã được duyệt che thông tin. Không trình bày bút toán nội bộ chưa duyệt như báo cáo công khai.

Sao lưu bằng `scripts/backup_pethome.ps1`: cả dump PostgreSQL và volume ảnh, manifest SHA256, kiểm tra dung lượng và giới hạn mặc định 500 MB ảnh. Script không tự xóa bản cũ. `-CopyTo` nhận thư mục NAS/ổ ngoài máy do người vận hành chỉ định và kiểm tra checksum sau sao chép. Có sidecar tùy chọn trong `docker-compose.backup.yml`: chỉ thêm file này sau khi điền `BACKUP_HOST_DIR` là NAS/ổ sao lưu đã được xác nhận ngoài ổ ứng dụng. Bật bằng `--profile backup`, chu kỳ mặc định một ngày, tối đa 64 MB RAM và kiểm tra checksum. Giới hạn tổng mặc định 5 GB; tới ngưỡng sẽ báo lỗi và giữ bản cũ, không xóa bừa hoặc làm đầy ổ. Kiểm tra `last-success.json` và log; chuyển bản cũ sang kho lưu đã kiểm chứng khi cần. Chưa có đích ngoài máy nên sidecar chưa được bật và chưa khẳng định đã có backup offsite. Với server Linux có thể dùng `scripts/backup_pg.sh` làm đầu vào DB, nhưng vẫn cần sao lưu ảnh và kiểm tra khôi phục như trên.

Sau khôi phục: để `RESCUE_AUTOMATION_PAUSED=true`; so tiền ngân hàng đã phát sinh, bé đã bàn giao, nơi và người chăm sóc thực tế, hiện vật đã nhận với bản khôi phục. Chỉ chạy lại job khi người chịu trách nhiệm xác nhận thực tế. Tham chiếu nghiệp vụ phải được giữ khi nhập bù. RPO 15 phút/RTO 2 giờ trong tài liệu là mục tiêu cần cấu hình lưu WAL/offsite và đo, chưa phải kết quả đã đạt.

Staging local độc lập có `docker-compose.staging.yml` và `.env.staging.example`. Tạo secret mới, dùng `docker compose --env-file .env.staging -f docker-compose.staging.yml up -d` khi có đủ RAM; truy cập loopback cổng 8080. Không chia sẻ volume/network của bản đang chạy, không dùng thông tin nhận tiền thật. Không tự chạy thêm bộ staging trên máy ít RAM. Bản staging HTTP chỉ phục vụ nghiệm thu local; triển khai Internet cần HTTPS và tên miền được cấu hình riêng.

## Điều kiện nghiệm thu ngoài phần mềm

Trạm còn phải cung cấp số/link thật, lịch trực/đầu mối, dữ liệu bé và quyền dùng ảnh, sức chứa đã kiểm tra, chính sách nhận nuôi và đóng góp, người đối soát, đích sao lưu và tên miền/email khi dùng. Pilot cần người của trạm làm một ca, một bàn giao và một kỳ đối soát bằng chứng từ thật. Code và kiểm thử giả lập không thay thế các xác nhận này.
