# Bàn giao SEO PetHome — 07/11/2026

## Đã thực hiện trong code

- Trang sản phẩm có title/description riêng, ưu tiên trường SEO hiện có ở backend và tự lấy tên/mô tả sản phẩm khi chưa nhập.
- Trang chủ, Shop và danh mục có metadata riêng. Canonical và thông tin chia sẻ dùng tên miền được cấu hình; trang phân trang danh mục có URL chuẩn riêng.
- Bổ sung `/sitemap.xml` từ danh mục và toàn bộ sản phẩm công khai, đọc theo từng trang API. Sitemap chưa có URL khi chưa cấu hình tên miền chính thức.
- Bổ sung `/robots.txt` trong ứng dụng; bản thử nghiệm mặc định chặn lập chỉ mục. Khi mở bán, Google được đọc các trang công khai.
- Các trang quản trị, tài khoản, đăng nhập/đăng ký, quên mật khẩu, giỏ hàng, thanh toán, tra đơn và tìm kiếm nội bộ có header noindex riêng. Điều này tiếp tục áp dụng khi bật lập chỉ mục cho trang bán hàng.
- Trang sản phẩm có JSON-LD Product/Offer khi đã cấu hình tên miền, với tên, giá VND và tồn kho của các biến thể đang hoạt động. Chỉ khai báo ảnh sản phẩm khi đã có ảnh tải lên; không khai báo đánh giá giả.
- Thẻ sản phẩm và trang chi tiết ưu tiên ảnh đã tải lên trong quản trị, có alt theo tên sản phẩm. Sản phẩm chưa có ảnh vẫn có ảnh thay thế.
- Bổ sung liên kết phân trang danh mục khi có đủ 48 sản phẩm/trang.

## Việc chủ shop cần làm

Bản Next.js đã được build và cập nhật Docker. Kiểm tra TypeScript đạt; script `qa-e2e/scripts/verify-seo.cjs` đạt ở chế độ mở bán mô phỏng bằng tên miền `https://seo-check.example` trong container riêng, sau đó đạt ở bản local và link public trong chế độ thử nghiệm. Đã kiểm tra tiêu đề sản phẩm/danh mục, canonical sản phẩm và trang phân trang, JSON-LD giá VND, sitemap, robots.txt và header noindex của tài khoản. Container kiểm tra riêng đã được dọn. Đây chưa phải xác nhận Google đã lập chỉ mục hoặc xác nhận Rich Results từ Google.

Link bản test khi bàn giao: https://orchestra-charge-contacted-taken.trycloudflare.com/ (link tunnel có thể thay đổi khi khởi động lại).

| Thứ tự | Bạn cần làm/cung cấp | Kết quả cần có |
|---|---|---|
| 1 | Chọn và sở hữu tên miền chính thức; chọn nơi chạy web liên tục | Tên miền HTTPS ổn định và quyền cấu hình DNS/máy chủ |
| 2 | Xác nhận tên shop, số điện thoại, Zalo, Facebook, địa chỉ và giờ làm việc thực tế | Thay các liên kết mạng xã hội mẫu trong cấu hình; nội dung liên hệ chính xác |
| 3 | Kiểm tra các sản phẩm bán thật, tải ảnh thật, điền thương hiệu, mô tả và quy cách | Các trang được đưa vào Google có dữ liệu thật và đúng giá/tồn kho |
| 4 | Rà soát danh mục `/c/test-qa-xoa` và các dữ liệu QA khác | Xác nhận dữ liệu nào là test trước khi ẩn khỏi shop; không xóa lịch sử nghiệp vụ |
| 5 | Xác nhận chính sách giao hàng, phí ship, đổi trả và khu vực phục vụ | Thay nội dung mẫu bằng chính sách shop thực sự áp dụng |
| 6 | Sở hữu tài khoản Google Search Console cho tên miền; xác minh bằng DNS | Gửi sitemap và dùng kiểm tra URL để xem Google có đọc/lập chỉ mục được không |
| 7 | Chuẩn bị Merchant Center; Business Profile nếu đủ điều kiện | Hoàn thiện thông tin kinh doanh và xác minh theo yêu cầu Google |
| 8 | Sau khi có khách: nhận đánh giá thật và theo dõi đơn từ tìm kiếm | Đánh giá nội dung dựa trên lượt hiển thị, nhấp và đơn hàng thực |

## Cấu hình khi triển khai tên miền thật

Người triển khai đặt trong `.env`:

```dotenv
SITE_URL=https://ten-mien-thuc-te-cua-ban.vn
SEO_ALLOW_INDEXING=true
```

Thay tên miền ví dụ bằng tên miền sở hữu thật. Chạy lại dịch vụ Next.js bằng `docker compose up -d nextjs`. Các giá trị được đọc lúc chạy; không cần build riêng cho từng tên miền.

Sau triển khai, kiểm tra lại các URL sản phẩm, `/robots.txt` và `/sitemap.xml`. Trang bán hàng phải không nhận `X-Robots-Tag: none/noindex` từ lớp proxy/CDN. Link `trycloudflare.com` đang có header chặn này từ lớp public, nên vẫn dùng để thử nghiệm. Không bật SEO bằng cách trỏ tên miền chuẩn về một link thử nghiệm.

Canonical/sitemap không bảo đảm Google lập chỉ mục hay tăng thứ hạng. Search Console của chủ tên miền là nơi kiểm tra kết quả thực tế.

## Giới hạn còn lại

- Chưa có tên miền hoặc tài khoản Google được cấp quyền để xác minh/đăng ký thực tế.
- Chưa nghiên cứu lượng tìm kiếm và mức cạnh tranh của từng từ khóa; chưa triển khai lịch bài viết.
- Chưa đo Core Web Vitals trên thiết bị người dùng hoặc Lighthouse cho tên miền production. Ảnh tải lên hiện được phục vụ trực tiếp; cần đánh giá dung lượng ảnh thật khi có danh mục chính thức.
- Chưa thêm giao diện biên tập SEO riêng trong quản trị; metadata tự sinh dùng được ngay, trường SEO backend hiện có được ưu tiên nếu đã nhập qua API.
- Để cấu hình tên miền được đọc đúng lúc chạy, các trang được kết xuất động. Cần theo dõi tài nguyên máy chủ sau khi có lưu lượng thực.

Đối chiếu hiện trạng trước sửa: `docs/kiem-tra-seo-pethome-2026-11-07.md`.
