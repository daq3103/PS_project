# Vận hành Trạm cứu hộ

Phân hệ dùng chung tài khoản Petshop. Khách xem tin công khai; đăng tin, báo cáo, xem liên hệ và gửi hồ sơ cần đăng nhập. Owner/CSKH quản lý tin nhận nuôi, kiểm duyệt và bàn giao tại `/admin/community`; nhân viên kho không có quyền cứu hộ quản trị.

## Phạm vi đã triển khai

- Tin mất/nhặt được: upload, đăng, sửa với version check, duyệt lại, đóng, xác nhận đoàn tụ và gửi duyệt mở lại.
- Feed có bốn lựa chọn gồm tất cả và ba loại tin, bộ lọc trong URL, cursor; liên kết chi tiết vẫn xem được khi tin đã giải quyết nhưng không trả liên hệ.
- Nhận nuôi: staff đăng từng bé, thành viên gửi/rút hồ sơ, staff liên hệ → chọn người nhận → xác nhận bàn giao. Khóa bài và partial unique index ngăn chọn hai người.
- Báo cáo vi phạm, lịch sử thao tác, trang theo dõi vận hành và thông báo trong tài khoản.
- Rate limit, xác minh Turnstile phía server, feature flag, giới hạn dung lượng/điểm ảnh, xóa EXIF và dọn upload bỏ dở.
- Outbox bền vững, nhắc hạn, hết hạn tin, giữ tin nhận nuôi có hồ sơ đang xử lý để staff xem lại và ẩn danh hồ sơ hết thời hạn.

MVP tiếp tục dùng **storage local riêng tư trên volume `community_uploads`**, theo phần đã có của project. Ảnh được encode JPEG trước khi lưu, phục vụ qua endpoint kiểm tra quyền, no-store; không dùng public static mount. Chưa chuyển sang R2/presigned upload. Nếu triển khai nhiều máy API/worker, cần chuyển sang object storage chung hoặc shared filesystem trước khi nhân rộng.

Danh mục khu vực `backend/app/modules/community/locations.json` có version `petshop-legacy-v1`, giữ nguyên 63 ID nội bộ từ form cũ để không đổi nghĩa dữ liệu đã có. Đây không phải danh mục hành chính chính thức hiện hành hay mã GHN. Server kiểm tra ID và lấy tên từ danh mục, không tin tên client gửi. Chưa có danh mục district/ward có mã: dùng tên tự nhập; server từ chối district_id/ward_code chưa được xác thực. Khi thay nguồn địa phương, phải tạo phiên bản và mapping cho dữ liệu cũ, không đổi tên một ID tại chỗ.

## Cấu hình

| Biến | Ý nghĩa |
|---|---|
| `COMMUNITY_ENABLED` | `false` trả 503 cho API cứu hộ, ẩn mục header; public config vẫn đọc được |
| `COMMUNITY_UPLOAD_DIR` | Mặc định `/app/data/community-uploads`, API và worker cần cùng volume |
| `COMMUNITY_TURNSTILE_SITE_KEY` | Public site key cho widget; lấy qua API config, không cần build lại frontend |
| `COMMUNITY_TURNSTILE_SECRET` | Secret chỉ ở backend |
| `COMMUNITY_TURNSTILE_HOSTNAME` | Hostname kỳ vọng của kết quả xác minh khi đã cấu hình |
| `COMMUNITY_RETENTION_DAYS` | Mặc định 90 ngày, tính từ lần cập nhật cuối của hồ sơ kết thúc |
| `TRUSTED_PROXY_CIDRS` | Subnet proxy thực tế; rỗng thì không tin X-Forwarded-For |
| `TRUST_PROXY_HEADERS` | Next.js chỉ bật sau ingress Nginx đã ghi đè X-Forwarded-For |
| `JWT_CLOCK_SKEW_SECONDS` | Dung sai đồng hồ JWT, mặc định 30 giây, giới hạn 0–60 |

`APP_ENV=development` cho phép chạy không có Turnstile. Môi trường khác thiếu secret sẽ từ chối đăng tin bằng 503. Cần cấu hình đúng cặp key và hostname trước khi mở public. Frontend CSP cho phép widget tại `challenges.cloudflare.com`.

Compose bind cổng Next.js và API về loopback, chỉ Nginx public. Nginx ghi đè X-Forwarded-For bằng địa chỉ kết nối và Next.js chuyển tiếp khi bật cấu hình; Uvicorn không tự diễn giải proxy headers. Thu hẹp `TRUSTED_PROXY_CIDRS` về subnet Docker thực tế khi vận hành. Nếu có CDN/reverse proxy trước Nginx, cấu hình trusted real-IP tại ingress theo hạ tầng thật; không tin thẳng header IP do client gửi.

Không lưu dữ liệu nhạy cảm trong unique_key outbox, log hoặc metadata công khai. Ghi chú nội bộ nhận nuôi không thuộc response thành viên. Tin chỉ mở liên hệ khi approved, open và chưa quá hạn.

## Luồng quản trị

1. Vào `/admin/community`, lọc tin pending, mở chi tiết để xem nội dung/ảnh, rồi duyệt hoặc từ chối kèm lý do. Các mutation cần TOTP.
2. Tin bị sửa được đưa về pending và tạm ẩn khỏi public. Lịch sử ở drawer giúp biết ai đã thay đổi trạng thái.
3. `/admin/community/new` tạo một tin cho một bé; các giá trị tiêm phòng/triệt sản cho phép chưa biết.
4. `/admin/community/adoptions`: ghi nhận liên hệ, chọn người nhận, xác nhận bàn giao thực tế. Bước chọn không đổi bài thành đã nhận nuôi. Bước bàn giao kết thúc các hồ sơ còn lại.
5. `/admin/community/reports`: xem bài bị báo cáo, nhập lý do rồi bác bỏ hoặc gỡ bài. Gỡ tin nhận nuôi kết thúc hồ sơ đang xử lý; không hủy kết quả bàn giao đã hoàn tất.
6. `/admin/community/metrics`: xem tin chờ lâu nhất, báo cáo chưa xử lý, hồ sơ đang xử lý, kết quả và tác vụ tồn/lỗi.

Thành viên xem `/account/community` để quản lý tin và đọc thông báo; `/account/adoption-requests` để theo dõi hoặc rút hồ sơ. Tin adoption cần thao tác quản trị có TOTP, kể cả người đăng là chủ tin.

## Worker và phục hồi lỗi

- `dispatch_community_outbox`: mỗi phút, claim tối đa 50 job với lease 5 phút; retry tăng dần, tối đa 8 lần rồi failed. Job processing quá lease được nhận lại. Insert thông báo và mark done cùng transaction; unique_key ngăn nhân đôi.
- `maintain_community_posts`: phút 5, 20, 35, 50. Nhắc trước 3 ngày; tin open không có hồ sơ nhận nuôi đang xử lý sẽ expired khi quá hạn. Duyệt mở lại sẽ có TTL mới.
- `cleanup_community_data`: 03:15 theo timezone worker. Dọn upload không được tham chiếu sau 24 giờ; quét file mồ côi; xóa thông tin cá nhân và ghi chú trong hồ sơ terminal đã quá retention.
- Khi Redis/worker tạm dừng, outbox vẫn nằm trong PostgreSQL. Khởi động lại worker rồi kiểm tra pending_jobs giảm.
- Khi failed_jobs tăng: kiểm tra log theo job ID và lớp lỗi, sửa nguyên nhân rồi đưa các job cần retry về pending bằng SQL có điều kiện, giữ nguyên unique_key. Không đặt lại toàn bộ job done.

Ví dụ retry sau khi đã sửa nguyên nhân, chạy có chủ đích với ID đã kiểm tra:

```sql
UPDATE community_job_outbox
SET status = 'pending', scheduled_at = NOW(), locked_until = NULL,
    attempt_count = 0, last_error = NULL
WHERE id = '<job_uuid>' AND status = 'failed';
```

## Kiểm thử

Kết quả kiểm tra local: 12 test backend qua trên PostgreSQL riêng; 4 test Playwright desktop/mobile qua; TypeScript, frontend lint, production build, ruff và mypy cho module mới đều qua. Đã thử migration 0003 → 0002 → 0003 trên DB tạm và kiểm tra cú pháp Nginx. Những kết quả này không thay thế UAT trên hostname và key Turnstile của môi trường phát hành.

Backend dùng database ngẫu nhiên có prefix `petshop_community_test_`. Script tạo database mới từ kết nối được cấu hình, migrate, chạy pytest, thử downgrade 0003 → 0002 → upgrade và chỉ xóa đúng database do lần chạy đó tạo. Tài khoản PostgreSQL test cần quyền CREATEDB. Không đặt test lên database shop.

```bash
cd backend
pip install -e ".[dev]"
python scripts/test_community.py
ruff check app tests
mypy app/modules/community app/worker/community_tasks.py
```

Frontend:

```bash
cd frontend
npm run lint
npx tsc --noEmit
npm run build
```

Playwright mới ở `qa-e2e/tests/05-community.spec.ts`. Chạy bằng API QA riêng:

1. Trong container backend dùng source mới, chạy `python scripts/community_qa.py`, publish cổng loopback 18000 → 8000. Script tạo database/tài khoản tổng hợp và ghi `/tmp/community-qa.json`.
2. Copy fixture đó vào `qa-e2e/community-qa.json` (đã gitignore, không dùng tài khoản thật).
3. Build frontend, khởi động với `INTERNAL_API_URL=http://127.0.0.1:18000`, `TRUST_PROXY_HEADERS=false` tại port 3100. Nếu frontend ở Docker, dùng hostname container API QA thay localhost.
4. Chạy `BASE_URL=http://127.0.0.1:3100 npx playwright test tests/05-community.spec.ts --project=desktop --project=mobile` trong `qa-e2e` (PowerShell dùng `$env:BASE_URL=...`).
5. Dừng API QA bằng SIGTERM để script đóng server và xóa đúng database tạm. Xóa fixture tài khoản QA khi xong. Không dùng `docker kill` trước bước dọn database.

Bộ CI backend đã có PostgreSQL/Redis và chạy test bằng script riêng, nên các test tranh chấp không bị bỏ qua trong CI. UAT trên hostname public với Turnstile thật vẫn cần cặp key của môi trường đó.

## Cập nhật môi trường và rollback

1. Backup PostgreSQL và volume ảnh trước cập nhật. Hai backup cần giữ cùng thời điểm; kiểm tra restore trên môi trường riêng.
2. Build image mới. API chạy Alembic khi khởi động; revision mới là `0003`.
3. Khởi động API, worker, frontend và reload Nginx; kiểm tra route `/api/proxy/api/v1/community/config` lẫn `/api/v1/community/config`.
4. Smoke test lost/found → duyệt → đóng và adoption → đăng ký → bàn giao bằng tài khoản thử được phép.
5. Theo dõi metrics và log, thống nhất người phụ trách duyệt tin trước khi public.

Nếu có lỗi, tắt `COMMUNITY_ENABLED` trên API/worker rồi recreate để áp dụng. Giữ nguyên dữ liệu và migration để sửa tiếp. Không downgrade xóa bảng trên môi trường có dữ liệu thật làm cách rollback mặc định.

## Backlog sau MVP

Bình luận/ghim, poster QR, gợi ý sản phẩm, đăng tin khách vãng lai và ghép tin lost/found vẫn là backlog mục 9 của plan. Những phần này chưa thuộc đợt hoàn thiện MVP. R2 và danh mục địa phương mới là các thay đổi hạ tầng/dữ liệu cần đầu vào môi trường cụ thể như mô tả ở trên.
