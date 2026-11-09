# Kiểm tra SEO PetHome — 07/11/2026

## Phạm vi và kết luận

Đã đọc code Next.js/FastAPI và kiểm tra 17 đường dẫn công khai trên `https://orchestra-charge-contacted-taken.trycloudflare.com`. Đối chiếu thêm phản hồi HTTP trực tiếp qua nginx local và yêu cầu có User-Agent Googlebot. Không đăng nhập, không thay đổi nội dung kinh doanh, không triển khai thay đổi ứng dụng.

PetHome có nội dung sản phẩm được kết xuất từ máy chủ và liên kết danh mục/sản phẩm trong HTML. Tuy nhiên, bản public hiện tại gửi `X-Robots-Tag: none`, tương đương `noindex, nofollow`. Đây là trở ngại trực tiếp đối với việc xuất hiện trên Google. Chỉ dẫn không có trong phản hồi local; bằng chứng cho thấy nó được thêm ở lớp phục vụ public/tunnel. Không thể giải quyết bằng cách thêm meta `index` vào trang vì Google áp dụng quy tắc hạn chế hơn.

Không kết luận trang đã hoặc chưa có trong chỉ mục thực tế của Google: việc này cần kiểm tra Search Console của tên miền chính thức.

## Các phát hiện

| Ưu tiên | Phát hiện có bằng chứng | Hướng xử lý |
|---|---|---|
| Trước khi mở bán | Toàn bộ 17 phản hồi public có `X-Robots-Tag: none`; yêu cầu với User-Agent Googlebot cũng nhận chỉ dẫn này. `/shop` qua local không có header đó. | Chốt tên miền chính thức và cấu hình nơi phục vụ production; kiểm tra header trên tên miền thật. Giữ bản thử nghiệm không được lập chỉ mục. |
| Cao | `/sitemap.xml` trả 404. Không tìm thấy route sitemap trong source. | Tạo sitemap tự cập nhật từ danh mục/sản phẩm đang công khai, dùng tên miền chuẩn. Sitemap giúp khám phá URL, không bảo đảm được lập chỉ mục. |
| Cao | 3 trang sản phẩm và 2 danh mục được kiểm tra dùng cùng title/description chung của thương hiệu. | Tạo metadata riêng theo từng sản phẩm/danh mục. Backend đã có `seo_title` và `seo_description`, nhưng trang sản phẩm hiện chưa sử dụng. |
| Cao | Tất cả trang mẫu không có canonical; URL danh mục `?sort=price_asc` cũng không có. | Quy định URL chính cho mỗi trang và xử lý URL lọc/sắp xếp, tránh nhiều bản nội dung tương tự. Không gộp máy móc các trang phân trang có sản phẩm khác nhau. |
| Cao | `/cart`, `/checkout`, `/login`, `/account/profile`, `/admin`, `/track-order` không có robots riêng trong HTML. Hiện chúng được chặn bởi header public toàn cục. | Thêm noindex ở ứng dụng cho các luồng này trước khi mở lập chỉ mục trang bán hàng. Noindex không thay thế xác thực/phân quyền. |
| Cao | Trang chi tiết dùng `coverFor()` để chọn ảnh minh họa chung. Pate và hạt cùng dùng `/brand/cat-food.jpg`; vòng cổ dùng `/brand/cat-accessories.jpg`. | Hiển thị ảnh sản phẩm được quản trị tải lên; chỉ dùng ảnh thay thế khi thiếu ảnh. Chủ shop cung cấp ảnh thật. |
| Trung bình | Không có JSON-LD trong các trang mẫu; chưa thấy code dữ liệu Product/Offer/Breadcrumb. | Thêm dữ liệu có cấu trúc theo sản phẩm/biến thể, giá và tồn kho thực. Không tự tạo đánh giá, chính sách hoặc thông tin thương hiệu chưa xác nhận. |
| Trung bình | HTML `/shop` vẫn có liên kết `/c/test-qa-xoa`. | Rà soát danh mục và dữ liệu thử nghiệm trước khi mở bán; xác minh đúng dữ liệu QA trước khi ẩn. Đợt kiểm tra này không xóa dữ liệu. |
| Trung bình | `SOCIAL_LINKS` trỏ đến trang gốc Zalo/Facebook/TikTok. Nội dung giao hàng/đổi trả ở trang sản phẩm đang viết cố định. | Cung cấp kênh chính thức và xác nhận chính sách thực tế trước khi công bố. |
| Khi tăng số sản phẩm | Trang danh mục chỉ lấy tối đa 48 sản phẩm, không có phân trang trong component này. | Bổ sung liên kết phân trang hoặc cách truy cập toàn bộ sản phẩm khi vượt 48. Hiện chưa kết luận đã có sản phẩm bị bỏ sót. |

## Những điểm đã ổn trong phạm vi kiểm tra

- Trang Shop, các danh mục và 3 sản phẩm mẫu trả HTTP 200 qua HTTPS.
- Tên sản phẩm và tiêu đề H1 đã nằm trong HTML ban đầu, không cần thao tác tìm kiếm mới thấy nội dung.
- Trang Shop có liên kết `<a href>` trực tiếp đến danh mục và sản phẩm; đây là nền tảng để trình thu thập dữ liệu khám phá các trang.
- HTML trang bán hàng có `lang="vi"` và viewport cho thiết bị di động.
- URL sản phẩm không tồn tại trả HTTP 404 và có meta `noindex`.
- Ảnh chính sản phẩm có alt theo tên sản phẩm.

## Lưu ý về robots.txt

Public `/robots.txt` trả 200 với nội dung ghi rõ Cloudflare Managed Content; trực tiếp local trả 404. Vì vậy, bản robots.txt hiện thấy trên tunnel không chứng minh ứng dụng đã có robots.txt riêng. Dòng `Allow: /` trong robots.txt không vô hiệu hóa `X-Robots-Tag: none`.

## Thứ tự triển khai đề xuất

1. Có thể chuẩn bị trong code: metadata riêng; sitemap; robots theo môi trường; canonical; noindex các trang chức năng; ảnh thật; dữ liệu sản phẩm có cấu trúc.
2. Cần chủ shop cung cấp: tên miền và nơi chạy chính thức, thông tin liên hệ, ảnh sản phẩm, chính sách giao hàng/đổi trả đã xác nhận.
3. Khi tên miền chạy: kiểm tra lại header, sitemap và truy cập Google; xác minh Search Console, gửi sitemap và kiểm tra URL đại diện.
4. Sau khi có dữ liệu: theo dõi trang được lập chỉ mục, truy vấn, lượt hiển thị, lượt nhấp và chuyển đổi thành đơn hàng.

## Giới hạn kiểm tra

- Chưa có quyền Search Console/Merchant Center; chưa đo lượng tìm kiếm, thứ hạng hoặc hiệu quả bán hàng từ Google.
- Đây là kiểm tra code và HTTP/HTML, không phải kiểm thử Googlebot thật hoặc xác nhận Google đã render/lập chỉ mục.
- Các thời gian phản hồi ghi trong JSON là một lần tải qua tunnel; không phải điểm tốc độ di động, Lighthouse hoặc Core Web Vitals.
- Chưa đo LCP/INP/CLS hay kiểm tra trực quan đầy đủ trên thiết bị di động.
- Không chấm điểm SEO tổng hợp và không cam kết thứ hạng.

## Bằng chứng và tài liệu đối chiếu

- Kết quả máy đọc: `test-reports/seo/audit-2026-11-07.json`.
- Script đọc dữ liệu công khai: `qa-e2e/scripts/audit-seo.py`.
- [Google: robots meta và X-Robots-Tag](https://developers.google.com/search/docs/crawling-indexing/robots-meta-tag).
- [Google: cấu trúc website bán hàng](https://developers.google.com/search/docs/specialty/ecommerce/help-google-understand-your-ecommerce-site-structure).
- [Google: ra mắt website bán hàng](https://developers.google.com/search/docs/specialty/ecommerce/how-to-launch-an-ecommerce-website).
- [Google: dữ liệu sản phẩm có cấu trúc](https://developers.google.com/search/docs/appearance/structured-data/product).
