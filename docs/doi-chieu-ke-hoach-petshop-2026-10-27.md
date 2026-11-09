# Đối chiếu kế hoạch Shop trong PetHome

Nguồn: `D:/Download/ke_hoach_he_thong_petshop.docx`, bản đề xuất ngày 26/10/2026. Đối chiếu code ngày 27/10/2026. Tài liệu nguồn được trích nội dung tại `docs/ke-hoach-petshop-nguon.txt` để tiện tra cứu.

PetHome vẫn có hai khu vực ngang hàng là Trạm cứu hộ và Shop. Kế hoạch thương mại điện tử áp dụng cho Shop, không đổi toàn bộ nền tảng thành website chỉ bán hàng. Chính sách MFA áp dụng theo quyết định đã thống nhất: chủ cửa hàng xác minh khi đăng nhập, giữ trong phiên; nhân viên dùng các quyền được cấp.

## Những phần đã bổ sung trong lần đối chiếu này

- Báo giá 10 phút trước khi đặt hàng, hiển thị tiền hàng, giảm giá, phí giao và tổng cuối. Báo giá gắn chủ thể, nội dung và giá hiện tại; chưa giữ hàng. Tạo đơn mới phải có báo giá hợp lệ. API cũ tạo đơn không có `quote_id` sẽ được yêu cầu xem lại báo giá.
- Kiểm tra lại giá khi đã khóa mẫu sản phẩm; giá, số lượng và danh tính yêu cầu được dùng để kiểm tra việc gửi lại. Giữ khóa giỏ, coupon và kho theo thứ tự thống nhất. Gửi lại cùng yêu cầu nhận cùng đơn; có đường khôi phục đơn khi trình duyệt mất phản hồi.
- COD chờ nhân viên xác nhận, giữ hàng tối đa 24 giờ nếu chưa xác nhận. Đơn online chờ thanh toán 15 phút. Đơn đã xác nhận không bị cron thông thường nhả hàng.
- Lô hết hạn, bị khóa, hoặc thiếu hạn dùng của sản phẩm bắt buộc có hạn không được phân bổ. Kiểm tra lần nữa lúc bàn giao; dùng ngày Việt Nam. Biên hạn còn lại cấu hình bằng `INVENTORY_MIN_SHELF_LIFE_DAYS`.
- Đóng gói giữ nguyên lượng thực có; khi bàn giao mới trừ lượng thực có và lượng đã giữ trong cùng transaction. Đơn cũ đã trừ kho lúc đóng gói không bị trừ lần hai. Hủy các đơn cũ này phải qua nhân viên kiểm tra, không tự cộng lại hàng.
- Nhả giữ chỗ không ghi thành bút toán nhập hàng. Báo cáo lệch kho loại các bút toán nhả giữ chỗ từ phiên bản trước khỏi tổng biến động vật lý.
- Khóa coupon trước khi kiểm tra lượt theo khách; phân bổ giảm giá xuống từng dòng bằng số nguyên, tổng phân bổ đúng tổng giảm và không vượt tiền dòng. Dữ liệu cũ được bổ sung phân bổ từ số tiền đã lưu.
- Tác vụ tạo thanh toán, email xác nhận và tạo vận đơn thử được ghi cùng transaction vào `commerce_jobs`. Worker dùng lease và thử lại; công việc hết lượt vẫn nằm trong mục Việc cần xử lý. Không gửi lại toàn bộ email đơn gần đây mỗi hai phút.
- Callback thanh toán kiểm tra chữ ký, tiền tệ, tham chiếu và số tiền; chống lặp theo giao dịch. Thanh toán và hết hạn khóa chung đơn. Chỉ xác nhận sau khi nhận đủ tiền; ghi nhận tiền đến sau hủy thành khoản cần xử lý, không tự mở lại đơn hoặc tạo tồn giả. Commit trước khi trả xác nhận callback.
- Mục Việc cần xử lý cho chủ cửa hàng: xem tác vụ lỗi và khoản cần hoàn/đối chiếu; thử lại tác vụ; ghi nhận chứng từ đã xử lý thủ công. Hủy đơn đã thanh toán không đồng nghĩa đã hoàn tiền. Khoản trả dư được gộp vào nghĩa vụ hoàn khi hủy, tránh yêu cầu hoàn hai lần.
- Tích hợp payOS bằng trang thanh toán của nhà cung cấp, mã tham chiếu ổn định, xác thực response/webhook bằng HMAC, và tra cứu cùng tham chiếu khi kết quả tạo link chưa rõ. Chưa có khóa thì chỉ hiện COD. Không dùng callback mô phỏng trong môi trường production.
- Nhập vận đơn thực đã tạo với GHN/GHTK/Viettel Post/đơn vị khác; lưu người thao tác và lịch sử. Đây là cách vận hành thủ công, chưa phải gọi API tạo vận đơn tự động của các hãng.
- Khách có thể hủy trước bàn giao từ Đơn hàng của tôi. Tra cứu theo mã và điện thoại chỉ hoạt động trong phiên sở hữu đơn; liên kết email dùng token có hạn 7 ngày, đúng mục đích. Có yêu cầu gửi lại link vào email nhận đơn, giới hạn tần suất và không trả token qua API gửi lại.
- Hỗ trợ khách hàng: tạo yêu cầu có chủ đề, liên kết đơn của mình, trao đổi và theo dõi. Nhân viên chăm sóc khách hàng trả lời, đổi trạng thái và đóng yêu cầu. API kiểm tra sở hữu/quyền; thay đổi trạng thái được ghi trong lịch sử trao đổi.
- Tìm kiếm không dấu và theo mã hàng; sắp xếp giá tại DB trước khi phân trang; dùng EXISTS để nhiều mẫu cùng sản phẩm không làm hụt trang. Thêm lọc thương hiệu, độ tuổi đã khai báo, còn hàng và liên kết phân trang giữ bộ lọc.
- `/readyz` kiểm tra thực PostgreSQL và hai Redis, trả 503 khi phụ thuộc chưa sẵn sàng.

## Đối chiếu toàn bộ phạm vi kế hoạch

| Mục của plan | Hiện trạng | Phần còn thiếu để đạt đầy đủ |
|---|---|---|
| 1 Danh mục và mua sắm | Có danh mục, sản phẩm, mẫu hàng, ảnh URL, tìm kiếm và lọc; sửa tìm không dấu/SKU và phân trang giá | Banner có lịch, quản lý thuộc tính theo nhóm đầy đủ, ảnh theo mẫu khi chọn, so sánh/yêu thích/đánh giá từ người mua |
| 2 Tài khoản và sau mua | Có đăng ký/đăng nhập, reset, phiên, địa chỉ, giỏ, đơn, hủy, tra cứu có quyền và hỗ trợ | Xác minh email đăng ký; ảnh minh chứng riêng tư; gắn đơn vãng lai qua xác minh email; hồ sơ thú cưng/mua lại P1 |
| 3 Quản trị | Có sản phẩm/danh mục, lô, điều chỉnh, đơn, coupon, quyền kho/CSKH và các màn hình mới | Vai trò nội dung và đối soát riêng; audit giá/cấu hình đầy đủ; tạo đơn hộ; nhà cung cấp và phiếu nhập; dashboard cảnh báo tổng hợp |
| 4 Kho và lô | Có giữ hàng FEFO, giá vốn lô, chống vượt tồn, kiểm tra hạn dùng và bàn giao | Giao diện cách ly/kiểm định và kiểm kê đầy đủ; tính biên theo ngày giao dự kiến thực; nhiều kho thuộc phần mở rộng |
| 5 Kiến trúc | Modular monolith, API/worker riêng, PostgreSQL, Redis, reverse proxy | Object storage/CDN ảnh sản phẩm; URL ảnh khiếu nại riêng tư; adapter hãng giao hàng thực |
| 6 Dữ liệu | Có Product/SKU/Lot, đơn snapshot, allocations, payments, events; thêm quote, outbox, cases và hỗ trợ | Payment attempts nhiều lần theo quy trình đầy đủ; returns/refunds theo dòng; coupon theo nhóm; job runs/audit tổng quát |
| 7 API | Có các endpoint nền và mới, kiểm tra quyền/phân trang/xung đột | Chuẩn hóa toàn bộ `error_code`, `field_errors`, `request_id`; API đổi trả và hoàn từng dòng |
| 8 Báo giá/đặt đơn | Đã bổ sung báo giá, kiểm tra giá, phân bổ giảm, giữ kho/coupon và outbox | Quy tắc thuế, freeship theo vùng/nhóm và chính sách đã được chủ duyệt |
| 9 Trạng thái/cạnh tranh | Có trạng thái đơn, thanh toán, giao; sửa khóa, hết hạn và bàn giao | Phân tách reservation ACTIVE/COMMITTED thành trục dữ liệu riêng nếu mở rộng; trạng thái đối soát COD chi tiết |
| 10 Thanh toán/hoàn | Có COD, mã tích hợp payOS, callback và khoản cần xử lý thủ công | Khóa kênh payOS thật, thử thu tiền thực; quy trình duyệt/thực hiện hoàn một phần và kiểm tra ngân hàng/cổng; màn hình đối soát giao dịch không khớp |
| 11 Giao/hủy/đổi trả | Có đóng gói, bàn giao, vận đơn thủ công, hủy có kiểm soát và yêu cầu hỗ trợ đổi trả | Đổi trả theo dòng/số lượng, tiếp nhận kiểm định, nhập lại hàng đủ điều kiện; COD settlement theo đợt; đối soát trạng thái giao thực |
| 12 Tác vụ nền | Có outbox bền vững, lease, thử lại và thao tác chạy lại | Đối soát payOS định kỳ ngoài webhook; cảnh báo chủ động; lịch sử từng lần chạy và timeout không rõ kết quả ở mọi adapter |
| 13 Bảo mật/chất lượng/SEO | Có Argon2, cookie/CSRF, phân quyền, giới hạn tần suất, MFA chủ shop, xử lý ảnh cứu hộ, đo hiệu năng | SEO sản phẩm/canonical/sitemap/structured data; chính sách đã duyệt; tải ảnh sản phẩm an toàn; rà soát lưu giữ dữ liệu; đo tải theo kịch bản plan |
| 14 Triển khai/backup | Có Compose và cấu hình RAM thấp, CI, backup; lần này khôi phục thử và so dữ liệu trước/sau migration | Staging/production độc lập; sao lưu ngoài máy và WAL để hướng tới RPO 15 phút; đo RTO đầy đủ; diễn tập sự cố nhà cung cấp và cảnh báo ngoài website |
| 15 Lộ trình | Dùng P0 trước, P1/P2 sau; giữ Shop trong PetHome | Chưa triển khai mọi giai đoạn/P1/P2 trong một lần sửa |
| 16 Nghiệm thu | Có regression PostgreSQL và browser; các kết quả bên dưới | Các ca hoàn một phần, refund timeout, tích hợp hãng thực và mất kết nối nhà cung cấp cần hoàn thiện trước khi đánh dấu P0 đạt |
| 17 Phát hành | Có code/build/kiểm thử cho đợt này | Chưa đủ điều kiện tuyên bố sẵn sàng bán thật toàn bộ: cần chính sách, tài khoản dịch vụ, kiểm thử tiền thực, hoàn/đổi trả, staging và backup ngoài máy |

## Các bước cần làm tiếp theo

1. Chủ shop tạo kênh payOS, tự điền cấu hình bí mật ở `.env`, cấu hình email và địa chỉ website HTTPS cố định. Kiểm tra webhook của đúng kênh; không điền khóa vào frontend hoặc gửi khóa trong chat.
2. Hoàn thiện đổi trả theo dòng, duyệt hoàn, kiểm định hàng về và đối soát COD. Yêu cầu hỗ trợ chủ đề Đổi trả hiện chỉ là tiếp nhận trao đổi, chưa tự động nhập kho hoặc hoàn tiền.
3. Bổ sung ảnh minh chứng riêng tư, audit giá/cấu hình, xác minh email và quản lý nội dung/chính sách. Không công bố chính sách mẫu như nội dung đã được chủ shop duyệt.
4. Tạo staging, kiểm thử thu/hoàn với tài khoản được phép; backup ngoài máy và WAL; thử phục hồi với thời gian đo thực. Bản backup hiện chỉ ở máy local.
5. Chạy bài tải có ngưỡng dừng trên máy đủ tài nguyên, sau đó mới xác nhận quy mô phục vụ. Không suy ra sức tải từ số bài regression đã qua.

## Kết quả kiểm tra của đợt này

- 43 bài kiểm thử đã qua trong container tối đa 256 MB, database tạo ngẫu nhiên và xóa sau khi hoàn tất. Bao gồm tranh tồn cuối, idempotency, coupon đồng thời, giá/quote thay đổi, hạn dùng, đóng gói/bàn giao, hủy, callback payOS và hết hạn cạnh tranh, lease outbox, hỗ trợ và phân quyền.
- Kiểm tra chữ ký payOS bằng vector mẫu công khai từ tài liệu chính thức, không dùng khóa người dùng hoặc chuyển tiền thật.
- Khôi phục `pethome-before-plan-0010.dump` vào database thử, chạy migration 0009 → 0010: các trường nghiệp vụ cũ giữ nguyên qua so sánh số dòng và checksum. Database khôi phục thử đã được xóa; database shop không bị thay dữ liệu khi diễn tập.
- TypeScript và build Next.js qua; browser kiểm tra báo giá/COD, điều kiện hiện payOS, hỗ trợ khách, trạng thái nhân viên, màn hình vận hành và độ rộng 390/1280 px. Dùng dữ liệu giả, không gửi email hoặc thanh toán thực.
- Ảnh giao diện nằm trong `PetHome-screenshots/plan-*.png`.
- Đã cập nhật Docker local với cả `docker-compose.yml` và `docker-compose.4gb.yml`, migration `0010`. Trang chủ, checkout, hỗ trợ, tìm kiếm và `/readyz` đã được kiểm tra HTTP 200 sau khởi động. payOS chưa có khóa nên checkout hiện COD; cấu hình và các bước bật online ở `docs/thanh-toan-va-van-hanh-shop.md`.

## Nguồn tích hợp

- payOS API: https://payos.vn/docs/api/
- Quy tắc chữ ký: https://payos.vn/docs/tich-hop-webhook/kiem-tra-du-lieu-voi-signature/
- Giới thiệu giải pháp/phí công bố: https://payos.vn/solutions/ (kiểm tra ngày 27/10/2026; cần xem điều kiện của kênh/ngân hàng khi đăng ký).
- GHN: https://developer.ghn.vn/vi — đăng ký tài khoản tích hợp miễn phí không có nghĩa cước giao hàng miễn phí.
