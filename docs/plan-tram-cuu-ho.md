# Kế hoạch triển khai Trạm cứu hộ

Ngày lập: 21/10/2026. Cập nhật: đã triển khai code MVP, đang nghiệm thu. Trạng thái chi tiết ở mục 11; các ý tưởng sau MVP ở mục 9 vẫn là backlog.

Mục tiêu là bổ sung cổng cộng đồng tìm pet thất lạc, tìm chủ cho pet nhặt được và nhận nuôi vào Petshop hiện tại. Dùng chung FastAPI, PostgreSQL, Redis, ARQ, Next.js và tài khoản của shop. Không cần tách service hay thay lại hệ thống đăng nhập.

Kế hoạch dựa trên source hiện có và phần Community Rescue trong tài liệu `Dac_ta_ky_thuat_Petshop_v1.3_Cursor_Agent.doc.docx`. Các lựa chọn dưới đây là đề xuất triển khai, không phải toàn bộ đã được người dùng chốt.

## 1. Phạm vi và lựa chọn cho MVP

| Nội dung | Phương án đề xuất |
|---|---|
| Xem tin | Công khai, không cần đăng nhập |
| Đăng tin mất/nhặt được pet | Cần đăng nhập; tận dụng tài khoản hiện tại |
| Đăng tin nhận nuôi | Chỉ owner và cskh_staff |
| Nhận nuôi | Một bài tương ứng một bé; người gửi hồ sơ phải đăng nhập |
| Quản lý tin | Chủ bài sửa, đóng, xác nhận kết quả; staff xử lý theo quyền |
| Bình luận | Để giai đoạn sau; MVP liên hệ qua thông tin chủ bài |
| Thương mại | Gợi ý sản phẩm để sau; không phụ thuộc checkout |
| Ngoài phạm vi | Quyên góp, chat realtime, AI ghép ảnh, bản đồ bán kính, quản lý cơ sở cứu hộ/điều trị |

Khác với Word: MVP đề xuất chưa cho khách vãng lai đăng bài. Nếu giữ yêu cầu đó, bổ sung riêng luồng OTP hoặc liên kết quản lý bí mật có token lưu hash, hết hạn/thu hồi; không dùng số điện thoại hay ID bài làm bằng chứng sở hữu. Không dùng guest_token giỏ hàng để cấp quyền sửa tin.

## 2. Tích hợp với base hiện tại

- Thêm `backend/app/modules/community/` gồm router, schemas, service, permissions và state transitions; model ở `backend/app/models/community.py`.
- Đăng ký model trong `backend/app/models/__init__.py`, router trong `backend/app/main.py`.
- Thêm migration sau revision hiện tại `0001`; kiểm tra head khi bắt đầu. Không sửa migration đã chạy, không tạo lại bảng users.
- Giữ `refresh_tokens`, `totp_enabled` và cơ chế mã hóa hiện tại; không đổi sang tên bảng/cột trong Word chỉ để đồng bộ hình thức.
- Public/self-service API dùng `/api/v1/community`; thao tác staff dùng `/api/v1/admin/community` để đi qua TOTP hiện tại.
- Bổ sung quyền riêng cho owner/cskh_staff. `require_staff_user` hiện bao gồm nhân viên kho nên không đủ để phân quyền cứu hộ.
- Tận dụng component admin đang có. Không bắt buộc cài shadcn/ui hoặc TanStack chỉ vì tài liệu liệt kê chúng.
- Thêm API client và sinh lại OpenAPI types theo quy trình project.
- Kiểm tra đường gọi `/api/proxy`: browser hiện gọi qua Next.js nhưng Nginx có route `/api/` về FastAPI. Cần định tuyến riêng `/api/proxy/` về Next.js hoặc thống nhất cách gọi API, kiểm tra cả truy cập trực tiếp lẫn qua Nginx.

## 3. Quy tắc nghiệp vụ

### 3.1 Quyền

| Hành động | Khách | Thành viên | Nhân viên kho | Owner / CSKH |
|---|---|---|---|---|
| Xem bài đã duyệt | Có | Có | Có | Có |
| Đăng lost/found | Không | Có | Có, như thành viên | Có |
| Sửa/đóng tin của mình | Không | Có | Có | Có |
| Đăng adoption | Không | Không | Không | Có |
| Duyệt, gỡ, xử lý báo cáo | Không | Không | Không | Có, TOTP |
| Gửi/rút hồ sơ nhận nuôi | Không | Có | Có, như thành viên | Có, như thành viên |
| Xem hồ sơ nhận nuôi | Không | Chỉ hồ sơ mình | Chỉ hồ sơ mình | Có theo nhiệm vụ |
| Chọn người nhận, bàn giao | Không | Không | Không | Có, TOTP |

Kiểm tra quyền ở backend trên từng tài nguyên. Không tin `author_user_id`, trạng thái duyệt hoặc vai trò do client gửi. Không tự đăng ký nhận nuôi bài mình đăng. Ghi chú nội bộ không xuất hiện trong response của người đăng ký.

### 3.2 Trạng thái bài

- Kiểm duyệt: `pending → approved/rejected`; `approved → hidden` khi có vi phạm.
- Tin mất/nhặt được mới luôn pending. Tin adoption do staff tạo có thể approved, nhưng vẫn phải qua quyền và TOTP, ghi lịch sử.
- Chủ bài sửa nội dung, ảnh hoặc liên hệ: trả về pending và tạm ẩn khỏi public cho đến khi duyệt lại. MVP không lưu hai phiên bản hiển thị song song.
- Vòng đời: `open → resolved/closed/expired`; mở lại qua hành động riêng, kiểm tra quyền và xét duyệt lại.
- `resolved` nghĩa là đã đoàn tụ hoặc đã bàn giao; `closed` nghĩa là ngừng đăng, không được hiển thị như kết quả thành công.
- Chỉ bài approved mới được public. Bài pending/rejected/hidden phải không truy cập được từ feed, slug, metadata hoặc API public.
- Đề xuất hết hạn sau 30 ngày không xác nhận lại; nhắc trước 3 ngày. Tin nhận nuôi đang xử lý hồ sơ được đưa vào danh sách staff kiểm tra thay vì tự hết hạn.

### 3.3 Hồ sơ nhận nuôi

- Luồng: `pending → contacted → approved → completed`.
- Có `rejected` và `withdrawn`; quy định rõ chuyển trạng thái và lý do. Không cho tự rút sau completed.
- Chỉ nhận hồ sơ khi bài là adoption, approved và open.
- Tối đa một hồ sơ đang xử lý cho mỗi user/bài; không cho gửi lại khi đã completed.
- Tối đa một hồ sơ approved hoặc completed trên một bài. Khi đã chọn người nhận, tạm dừng nhận hồ sơ mới; nếu người đó rút, staff có thể chọn người khác.
- Duyệt và bàn giao phải khóa bản ghi bài trong transaction, kiểm tra trạng thái rồi cập nhật; thêm unique index có điều kiện làm lớp bảo vệ thứ hai.
- Chỉ completed mới chuyển bài sang resolved. Đóng các hồ sơ còn lại với lý do rõ ràng và ghi lịch sử trong cùng transaction.

## 4. Dữ liệu và ràng buộc

| Bảng | Nội dung cần có |
|---|---|
| `community_posts` | Trường trong Word; thêm found_at, expires_at, resolved_at, resolution_note, moderation_reason, moderated_at, moderated_by và version để chống ghi đè |
| `community_post_images` | post_id, upload_id/object_key, thứ tự, kích thước ảnh; chỉ tham chiếu upload hợp lệ |
| `community_uploads` | Người tải, object_key riêng tư, trạng thái pending/processing/ready/rejected, loại file, dung lượng, thời hạn |
| `adoption_requests` | Người gửi, thông tin liên hệ/điều kiện sống, trạng thái, người xử lý, thời điểm cập nhật/bàn giao, ghi chú nội bộ |
| `community_reports` | Người báo cáo, bài, lý do, trạng thái xử lý, người xử lý/thời điểm; tránh spam trùng |
| `community_audit_logs` | Actor, bài/hồ sơ, hành động, trạng thái trước/sau, lý do, thời điểm; hạn chế sao chép PII |
| `community_job_outbox` | Sự kiện cần gửi worker, khóa chống lặp, trạng thái gửi, lần thử; ghi cùng transaction nghiệp vụ |

Bảng comments chỉ thêm khi triển khai giai đoạn sau. Tách ảnh thay vì dùng `image_urls` JSONB để quản lý sở hữu và vòng đời upload rõ ràng.

Ràng buộc và kiểm tra:

- Tối đa 5 ảnh/bài; ảnh phải thuộc người tạo hoặc do staff được phép quản lý, trạng thái ready.
- `last_seen_at` cho lost_pet; `found_at` cho found_pet. Các trường không liên quan không được dùng lẫn.
- `adoption_meta` có schema Pydantic rõ: tuổi ước tính, kích thước, tiêm phòng, triệt sản, tình trạng sức khỏe và điều kiện nhận nuôi. Cho phép giá trị chưa biết, không ép thành false.
- Kiểm tra mã địa phương ở server theo một danh mục có phiên bản; lưu tên snapshot. Không mặc định dùng mã hãng vận chuyển làm danh mục cộng đồng; cho phép district không bắt buộc nếu nguồn địa phương không dùng cấp này.
- Index feed theo loại/khu vực/trạng thái và `(created_at, id)`; index hàng đợi duyệt, tin của tôi, hồ sơ theo bài/người gửi và báo cáo chưa xử lý.
- Phân trang cursor `(created_at, id)` để hạn chế trùng/bỏ sót khi có bài mới.
- ID và slug khó đoán không thay thế kiểm tra quyền. Idempotency key cho tạo bài và gửi hồ sơ, có kiểm tra payload khi retry.

## 5. API và màn hình

Prefix chung `/api/v1`:

| API | Mục đích |
|---|---|
| `GET /community/posts` | Feed approved, lọc loại/loài/khu vực/vòng đời, cursor |
| `GET /community/posts/{slug}` | Chi tiết public, không chứa liên hệ đầy đủ |
| `POST /community/posts/{id}/contact-reveal` | Xem liên hệ bài đang mở, kiểm tra chống lạm dụng; no-store |
| `POST /community/posts` | Tạo lost/found cho user đăng nhập |
| `GET /community/me/posts` | Tin của tôi, gồm pending/rejected |
| `PATCH /community/posts/{id}` | Sửa bài của mình, version check, kiểm duyệt lại |
| `POST /community/posts/{id}/close`, `/resolve`, `/renew` | Chuyển trạng thái có điều kiện; resolve adoption chỉ qua bàn giao |
| `POST /community/uploads/presign`, `/complete` | Cấp upload và bắt đầu kiểm tra/xử lý ảnh |
| `POST /community/posts/{id}/reports` | Gửi báo cáo, cần đăng nhập trong MVP |
| `POST /community/posts/{id}/adoption-requests` | Gửi hồ sơ |
| `GET /community/me/adoption-requests` | Xem hồ sơ của mình |
| `POST /community/adoption-requests/{id}/withdraw` | Rút hồ sơ của mình |
| `/admin/community/posts` | Danh sách quản trị, tạo adoption; action approve/reject/hide |
| `/admin/community/adoption-requests` | Danh sách/chi tiết; action contact/approve/reject/complete |
| `/admin/community/reports` | Danh sách và xử lý báo cáo |

Định nghĩa method, input/output và mã lỗi đầy đủ trong schemas/OpenAPI trước khi nối UI. Prefix tĩnh như `/me/posts` phải được đăng ký không xung đột route động. Trả 409 khi xung đột version/trạng thái; response public, của chủ bài và admin là các schema riêng.

Màn hình:

- `/tram-cuu-ho`: ba tab, bộ lọc, trạng thái tải/rỗng/lỗi, nút Đăng tin; bộ lọc được lưu trong query string.
- `/tram-cuu-ho/[slug]`: ảnh, đặc điểm, khu vực, thời gian, liên hệ, báo cáo, đăng ký nhận nuôi theo loại tin; chỉ hiện vị trí công khai ở mức người đăng đồng ý.
- `/tram-cuu-ho/dang-tin`: chọn lost/found, form theo loại, upload và xem trước.
- `/account/community`: tin của tôi, trạng thái duyệt và hành động quản lý.
- `/account/adoption-requests`: tiến độ hồ sơ và rút hồ sơ.
- `/admin/community`: hàng đợi duyệt, quản lý tin, báo cáo và nhận nuôi; có bộ lọc và nhật ký.
- Thêm mục Trạm cứu hộ vào SiteHeader và menu admin theo quyền, bảo đảm dùng được trên mobile và bàn phím.

## 6. Upload, riêng tư và chống lạm dụng

- Upload tối đa 5 MB/ảnh đầu vào, tối đa 5 ảnh. MVP nhận JPEG/PNG/WebP; decode, giới hạn số pixel, bỏ EXIF và encode lại ảnh. Không nhận SVG hoặc URL ảnh tùy ý từ client.
- Presigned URL ngắn hạn, object_key do server cấp; upload vào vùng riêng tư. Worker xác minh dung lượng/nội dung/quyền sở hữu trước khi ready. Chỉ công khai bản đã xử lý của bài được duyệt; gỡ bài phải thu hồi khả năng truy cập ảnh theo chính sách storage/cache đã chọn.
- Không coi Content-Type hoặc khai báo từ browser là bằng chứng file hợp lệ. Dọn upload bỏ dở sau 24 giờ; không xóa ảnh còn được tham chiếu.
- Turnstile xác minh server-side trước khi ghi bài. Rate limit cả cấp upload, tạo tin, gửi hồ sơ, báo cáo và xem liên hệ; kết hợp account với IP tin cậy.
- Mức ban đầu đề xuất: đăng tin 3/giờ/user và 10/giờ/IP; gửi hồ sơ 5/giờ/user; xem liên hệ 10/10 phút/user hoặc khách. Đây là thay đổi so với Word 3 bài/giờ/IP, cần điều chỉnh theo log sử dụng.
- Chuẩn hóa trusted proxy ở Nginx/Next.js/FastAPI. Không nhận nguyên giá trị X-Forwarded-For do client tự gửi; kiểm tra không gom mọi khách thành IP Next.js.
- Liên hệ đầy đủ chỉ trả ở endpoint riêng khi bài đang mở; closed/resolved/expired không tiết lộ. Turnstile cho khách xem liên hệ; không ghi số điện thoại vào log request/analytics.
- Hồ sơ nhận nuôi và endpoint riêng tư dùng no-store; SSR/metadata/feed không chứa SĐT đầy đủ hoặc địa chỉ người đăng ký.
- Chốt thời hạn giữ hồ sơ trước vận hành; đề xuất 90 ngày sau đóng, sau đó xóa/ẩn danh thông tin cá nhân không còn cần thiết. Có tác vụ thực thi và kiểm tra, không chỉ ghi chính sách.
- Nội dung MVP là plain text, render escaped; không dùng HTML do người dùng nhập.
- Không gọi Turnstile, R2 hay email trong transaction DB. Cẩn thận SQLAlchemy autobegin ngay khi đọc DB; kết thúc transaction trước external I/O. Sự kiện notification ghi outbox cùng dữ liệu, worker xử lý retry có chống lặp.

## 7. Các giai đoạn triển khai

Ước lượng dưới đây là ngày công của một lập trình viên quen stack, gồm kiểm thử và sửa lỗi thông thường; không phải cam kết lịch. Thời gian chờ tài khoản R2/Turnstile/email hoặc sửa lỗi nền phát sinh tính riêng.

| Giai đoạn | Đầu việc | Điều kiện hoàn thành | Ước lượng |
|---|---|---|---|
| 0. Chốt contract | Scope đăng nhập, quyền, trạng thái, API/schema, dữ liệu địa phương, chính sách liên hệ | Các lựa chọn ở mục 1–6 được thống nhất, có mẫu response | 1–2 ngày |
| 1. Nền và dữ liệu | Migration, models, permissions, trusted proxy, định tuyến Nginx, feature flag | Upgrade được DB cũ; quyền/TOTP/IP đúng trên hai đường truy cập | 2–3 ngày |
| 2. Tin mất và nhặt được | Upload, Turnstile, CRUD, duyệt, lịch sử, report, contact reveal | Một tin đi được từ tạo → duyệt → xem → đóng; kiểm tra quyền và riêng tư đạt | 3–5 ngày |
| 3. Giao diện cộng đồng | Feed, chi tiết, đăng tin, quản lý tin, admin duyệt/báo cáo | Luồng end-to-end chạy trên desktop/mobile; trạng thái rỗng/lỗi đầy đủ | 3–4 ngày |
| 4. Nhận nuôi | Tạo adoption, form hồ sơ, chọn người nhận, bàn giao, UI quản trị | Hai thao tác đồng thời không duyệt trùng; bàn giao cập nhật bài đúng | 3–4 ngày |
| 5. Vận hành và phát hành | Outbox/nhắc hạn, cleanup, monitoring, hồi quy shop, UAT, deploy staging | Checklist mục 8 đạt; có runbook và phương án tắt tính năng | 2–3 ngày |

Tổng dự kiến 14–21 ngày công, khoảng 3–5 tuần làm việc tùy thời gian review. Các phần kiểm thử đi cùng từng giai đoạn, không dồn toàn bộ đến cuối.

Mốc đầu tiên nên làm: migration + API lost/found + upload + admin duyệt + một trang feed tối thiểu. Kiểm chứng luồng này trước khi mở rộng nhận nuôi. Hạ tầng notification/outbox có thể triển khai ở giai đoạn 5 nếu các giai đoạn trước chưa gửi thông báo ra ngoài.

## 8. Kiểm thử và điều kiện phát hành

- Migration trên DB mới và bản sao DB hiện có; bảng shop và dữ liệu cũ vẫn nguyên vẹn. Downgrade chỉ kiểm tra trên DB dùng thử.
- Backend integration test dùng PostgreSQL thật cho khóa/unique index, không thay SQLite cho kiểm thử tranh chấp.
- Guest không đăng được; user A không sửa/xem dữ liệu riêng của user B; nhân viên kho không duyệt/đăng adoption; mutation staff thiếu TOTP bị từ chối.
- Pending/hidden không xuất hiện qua mọi đường public. Sửa bài approved đưa về pending đúng quy tắc.
- Request đóng tin và xem liên hệ phải có thứ tự nhất quán; sau khi đóng không phục vụ số từ cache. Kiểm tra HTML SSR, metadata và response JSON.
- Hai request duyệt khác người cùng một bé: chỉ một thành công; retry hoàn thành không ghi bàn giao/histories hai lần.
- Upload sai MIME, vượt dung lượng, ảnh có số pixel quá lớn, upload của người khác và URL tùy ý đều bị từ chối. EXIF không có trong ảnh public.
- Giả X-Forwarded-For không vượt giới hạn; hai người qua Next.js không bị nhận chung IP do proxy. Turnstile sai/hết hạn bị từ chối.
- Worker retry hoặc Redis tạm lỗi không làm mất sự kiện outbox; nhắc hạn và cleanup không chạy lặp gây tác dụng phụ.
- Playwright: đăng nhập → đăng lost/found → staff duyệt → tìm/lọc → đóng tin; đăng ký nhận nuôi → duyệt → bàn giao.
- Hồi quy đăng nhập, giỏ hàng, checkout và admin shop sau thay đổi proxy/middleware. Chạy ruff/mypy/pytest và TypeScript/lint/build theo cấu hình thực tế; sửa script lint nếu không tương thích toolchain hiện có.
- UAT trên staging có R2/Turnstile thật. Chốt ngưỡng latency với dữ liệu seed và môi trường cụ thể, không suy từ tốc độ local.

Phát hành: backup → migration bổ sung → deploy dưới feature flag → smoke test staff → mở cho người dùng. Khi có sự cố, tắt entry point và API community bằng flag, giữ dữ liệu để sửa; không dùng downgrade xóa bảng làm rollback production mặc định.

Theo dõi tối thiểu: số tin pending và tuổi tin lâu nhất, thời gian duyệt, tỷ lệ upload lỗi, tỷ lệ bị rate limit, báo cáo chưa xử lý, outbox tồn đọng, lỗi worker và kết quả đoàn tụ/bàn giao. Cần có người phụ trách duyệt tin; mục tiêu phản hồi ban đầu do người vận hành thống nhất.

## 9. Sau MVP

1. Bình luận đăng nhập, báo cáo/ẩn bình luận, ghim manh mối; huy hiệu và quyền ghim do server quyết định, không mặc định mọi nhân viên là quản trị cứu hộ.
2. Poster tải xuống có QR; số điện thoại mặc định tắt, chủ bài chọn bật. Thử CORS của ảnh trước khi xuất canvas; ảnh đã chia sẻ không thể thu hồi số điện thoại.
3. Gợi ý sản phẩm ở trang nhận nuôi hoặc sau khi đoàn tụ, không chen vào thông tin cấp thiết.
4. Đăng tin khách vãng lai có xác minh và cơ chế quản lý tin an toàn nếu thực sự cần giảm bước đăng nhập.
5. Tìm kiếm nâng cao, ghép tin lost/found theo loài/khu vực/thời gian sau khi có dữ liệu đủ dùng.

## 10. Thứ tự bắt tay vào code

- [x] Triển khai theo giả định MVP: đăng nhập khi đăng tin và một bài/một bé.
- [x] Viết schema/permission/state contract và test tình huống tranh chấp.
- [x] Tạo migration bổ sung và đăng ký models (revision 0003 sau 0002).
- [x] Sửa đường proxy/IP, bổ sung dependency quyền cứu hộ và giới hạn cổng public.
- [x] Làm upload và lost/found + duyệt bài.
- [x] Nối giao diện cộng đồng và admin vào API.
- [x] Thêm nhận nuôi, xử lý đồng thời và bàn giao.
- [x] Hoàn thiện outbox/thông báo trong tài khoản, tác vụ hết hạn, dọn ảnh, retention và hướng dẫn vận hành.
- [x] Playwright desktop/mobile, production build, TypeScript, backend lint/typecheck và cú pháp Nginx.
- [x] Thử migration 0003 → 0002 → 0003 trên database tạm riêng.
- [ ] Nghiệm thu staging qua ingress thực tế, Turnstile thật và kiểm tra tải theo môi trường.
- [ ] Cấu hình Turnstile thật, rà soát danh mục địa phương, backup/restore và phát hành môi trường thật.

## 11. Trạng thái nghiệm thu

Đợt hoàn thiện tiếp tục storage ảnh local riêng tư bằng volume Docker theo implementation đã có. R2/presigned upload chưa được triển khai; chi tiết lựa chọn storage, danh mục khu vực kế thừa và các thao tác vận hành nằm ở `docs/runbook-tram-cuu-ho.md`.

- Backend: 12 test đã qua trên PostgreSQL tạm riêng, bao gồm khóa đồng thời, ràng buộc chọn người nhận, idempotency, phân quyền/riêng tư, outbox recovery, retention, dọn ảnh và dung sai giờ JWT.
- TypeScript, production build, frontend lint và kiểm tra kiểu/lint backend đã qua. Cú pháp Nginx đã được kiểm tra.
- Playwright: 4/4 test qua trên desktop và mobile, bao gồm upload/duyệt/đoàn tụ và toàn bộ luồng nhận nuôi đến bàn giao. Có kiểm tra khung admin không tràn ngang trên viewport mobile.
- Migration: tạo DB mới từ revision 0001 đến 0003, chạy test, downgrade 0003 → 0002 rồi upgrade lại 0003 đều qua trên DB tạm.
- Chưa áp migration 0003 vào database shop và chưa phát hành production. Kiểm thử dùng database và tài khoản tổng hợp riêng; hướng dẫn chạy lại có trong runbook.

Không đánh dấu UAT/phát hành hoàn thành chỉ dựa vào source và test local. Sau khi có kết quả kiểm thử tiếp theo, cập nhật mục này theo kết quả thực tế.
