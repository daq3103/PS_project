# Liên hệ và mạng xã hội PetHome

Chỉnh tất cả địa chỉ tại `frontend/src/config/social-links.ts`. Hiện dùng link mẫu tới trang chủ Zalo, Facebook và TikTok theo yêu cầu; chưa phải tài khoản chính thức của PetHome.

```typescript
export const SOCIAL_LINKS = {
  zalo: "https://zalo.me/SO_DIEN_THOAI",
  facebook: "https://www.facebook.com/TEN_TRANG",
  tiktok: "https://www.tiktok.com/@TEN_TAI_KHOAN",
} as const;
```

Muốn nút Facebook dẫn thẳng tới cuộc trò chuyện thì dùng `https://m.me/TEN_TRANG`. Tên, mô tả và việc kênh nào xuất hiện trong tab Liên hệ nằm cùng file, trong `SOCIAL_CHANNELS`.

File cấu hình này dùng chung cho nút nổi và chân trang. Sau khi sửa cần build lại frontend và cập nhật container `nextjs`. Không cần thay database hoặc backend. Khi đang dùng cấu hình 4 GB, giữ cả `docker-compose.yml` và `docker-compose.4gb.yml` trong lệnh Compose.

Nút liên hệ chỉ hiển thị trong phần website dành cho người dùng, gồm trang chủ, Shop, cứu hộ và tài khoản. Bấm mở hai tab Liên hệ / Mạng xã hội; bấm ngoài bảng, nhấn Escape hoặc nút đóng để thu gọn. Có hỗ trợ bàn phím cho các tab, màn hình điện thoại và khoảng an toàn cuối màn hình. Các liên kết mở tab mới, không nhúng mã theo dõi hoặc cửa sổ chat của bên thứ ba.
