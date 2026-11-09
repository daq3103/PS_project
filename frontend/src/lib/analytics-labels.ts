const pageNames: Record<string, string> = {
  "/": "Trang chủ", "/shop": "Shop", "/search": "Tìm sản phẩm", "/cart": "Giỏ hàng",
  "/checkout": "Thanh toán", "/track-order": "Tra cứu đơn hàng",
  "/login": "Đăng nhập", "/register": "Đăng ký", "/forgot-password": "Lấy lại mật khẩu", "/reset-password": "Đặt mật khẩu mới", "/account": "Tài khoản của tôi",
  "/account/profile": "Thông tin cá nhân", "/account/orders": "Đơn hàng của tôi",
  "/account/addresses": "Sổ địa chỉ", "/account/community": "Tin cứu hộ của tôi",
  "/account/adoption-requests": "Hồ sơ nhận nuôi", "/tram-cuu-ho": "Trạm cứu hộ",
  "/tram-cuu-ho/dang-tin": "Đăng tin cứu hộ", "/p/[product]": "Chi tiết sản phẩm",
  "/c/[category]": "Danh mục sản phẩm", "/tram-cuu-ho/[post]": "Chi tiết tin cứu hộ",
  "/account/community/[post]/edit": "Chỉnh sửa tin cứu hộ",
};

export function analyticsPageName(path: string) {
  return pageNames[path] ?? "Trang khác";
}

export function analyticsActivityName(route: string) {
  const [method, ...parts] = route.split(" ");
  const path = parts.join(" ");
  const read = method === "GET" || method === "HEAD";
  if (path === "/unmatched") return "Truy cập không tìm thấy";
  if (path.includes("/contact-reveal")) return "Xem liên hệ người đăng tin";
  if (path.includes("/community/locations")) return "Tải danh sách khu vực";
  if (path.includes("/community/config")) return "Kiểm tra trạng thái trạm cứu hộ";
  if (path.includes("/community/uploads")) return read ? "Xem ảnh cứu hộ" : "Tải ảnh cứu hộ lên";
  if (path.includes("/community/me/posts")) return "Xem tin cứu hộ của tôi";
  if (path.includes("/adoption-requests")) return read ? "Xem hồ sơ nhận nuôi" : "Cập nhật hồ sơ nhận nuôi";
  if (path.includes("/notifications")) return read ? "Xem thông báo" : "Cập nhật thông báo";
  if (path.includes("/community/reports")) return read ? "Xem báo cáo tin cứu hộ" : "Xử lý báo cáo tin cứu hộ";
  if (path.includes("/community")) return read ? "Xem tin cứu hộ" : "Cập nhật tin cứu hộ";
  if (path.includes("/auth/login")) return "Đăng nhập";
  if (path.includes("/auth/logout")) return "Đăng xuất";
  if (path.includes("/auth/register")) return "Đăng ký tài khoản";
  if (path.includes("/auth/me")) return read ? "Kiểm tra tài khoản" : "Cập nhật tài khoản";
  if (path.includes("/totp")) return "Xác minh bảo mật";
  if (path.includes("/cart")) return read ? "Xem giỏ hàng" : "Cập nhật giỏ hàng";
  if (path.includes("/categories")) return read ? "Xem danh mục sản phẩm" : "Cập nhật danh mục sản phẩm";
  if (path.includes("/products")) return read ? "Xem sản phẩm" : "Cập nhật sản phẩm";
  if (path.includes("/addresses")) return read ? "Xem sổ địa chỉ" : "Cập nhật sổ địa chỉ";
  if (path.includes("/orders")) return read ? "Xem đơn hàng" : "Cập nhật đơn hàng";
  if (path.includes("/shipping")) return "Xử lý vận chuyển";
  if (path.includes("/payments") || path.includes("/webhooks")) return "Xử lý thanh toán và giao hàng";
  if (path.includes("/dashboard") || path.includes("/reports")) return "Xem báo cáo quản lý";
  if (path.includes("/inventory")) return read ? "Xem tồn kho" : "Cập nhật tồn kho";
  if (path.includes("/promotions")) return read ? "Xem khuyến mãi" : "Cập nhật khuyến mãi";
  if (path.includes("/reviews")) return read ? "Xem đánh giá" : "Cập nhật đánh giá";
  return read ? "Tải thông tin website" : "Xử lý thao tác trên website";
}
