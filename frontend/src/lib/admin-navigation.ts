type AdminLink = { href: string; label: string; permissions?: string[]; ownerOnly?: boolean };
type AdminGroup = { label: string; description: string; links: AdminLink[] };

export const STAFF_PERMISSION_LABELS: Record<string, string> = {
  warehouse: "Kho & giao hàng", customer_support: "Chăm sóc khách hàng",
  rescue_manage: "Quản lý trạm", rescue_care: "Chăm sóc các bé", rescue_finance: "Tài chính trạm",
  platform_manage: "Quản lý nền tảng (không cấp quyền)",
};

export const ADMIN_GROUPS: AdminGroup[] = [
  { label: "Điều hành", description: "Nắm tình hình chung và các việc cần ưu tiên.", links: [
    { href: "/admin", label: "Tổng quan" },
    { href: "/admin/operations", label: "Đối soát & công việc chờ", ownerOnly: true },
  ] },
  { label: "Trạm cứu hộ", description: "Tiếp nhận, chăm sóc và kết nối nhận nuôi tại Hà Nội.", links: [
    { href: "/admin/rescue", label: "Chăm sóc & tiếp nhận", permissions: ["rescue_manage", "rescue_care"] },
    { href: "/admin/rescue/coordination", label: "Lịch & điều phối trạm", permissions: ["rescue_manage"] },
    { href: "/admin/community", label: "Tin cứu hộ", permissions: ["rescue_manage"] },
    { href: "/admin/community/new", label: "Đăng nhận nuôi", permissions: ["rescue_manage"] },
    { href: "/admin/community/adoptions", label: "Hồ sơ nhận nuôi", permissions: ["rescue_manage"] },
    { href: "/admin/community/reports", label: "Báo cáo vi phạm", permissions: ["rescue_manage"] },
    { href: "/admin/rescue/finance", label: "Thu chi & đối soát trạm", permissions: ["rescue_finance"] },
    { href: "/admin/rescue/activity", label: "Báo cáo hoạt động trạm", permissions: ["rescue_manage"] },
    { href: "/admin/community/metrics", label: "Tình hình tin & nhận nuôi", permissions: ["rescue_manage"] },
  ] },
  { label: "Shop", description: "Quản lý bán hàng, sản phẩm và kho.", links: [
    { href: "/admin/shop", label: "Tổng quan Shop", permissions: ["warehouse", "customer_support"] },
    { href: "/admin/shop/insights", label: "Biểu đồ & chi phí", permissions: ["warehouse"] },
    { href: "/admin/orders", label: "Đơn hàng", permissions: ["warehouse", "customer_support"] },
    { href: "/admin/inventory-lots", label: "Kho & lô hàng", permissions: ["warehouse"] },
    { href: "/admin/products", label: "Sản phẩm", ownerOnly: true },
    { href: "/admin/categories", label: "Danh mục sản phẩm", ownerOnly: true },
    { href: "/admin/shop/menu", label: "Thanh menu Shop", ownerOnly: true },
    { href: "/admin/promotions", label: "Khuyến mãi", ownerOnly: true },
    { href: "/admin/reports", label: "Báo cáo bán hàng", permissions: ["warehouse"] },
  ] },
  { label: "Chăm sóc khách hàng", description: "Tiếp nhận hỗ trợ và phản hồi khách mua hàng.", links: [
    { href: "/admin/support", label: "Yêu cầu hỗ trợ", permissions: ["customer_support"] },
    { href: "/admin/reviews", label: "Đánh giá sản phẩm", permissions: ["customer_support"] },
  ] },
  { label: "Hệ thống", description: "Theo dõi hoạt động website, bảo mật và phân quyền.", links: [
    { href: "/admin/analytics", label: "Truy cập & hiệu năng", ownerOnly: true },
    { href: "/admin/staff", label: "Nhân viên & phân quyền", ownerOnly: true },
    { href: "/admin/settings", label: "Cài đặt bảo mật", ownerOnly: true },
    { href: "/admin/rescue/audit", label: "Lịch sử thay đổi trạm", ownerOnly: true },
  ] },
];

export function adminGroups(role?: string, permissions: string[] = []) {
  if (role !== "owner" && (!["warehouse_staff", "cskh_staff"].includes(role ?? "") || !permissions.some(p => p in STAFF_PERMISSION_LABELS))) return [];
  const manager = canManagePlatform({ role, staff_permissions: permissions });
  return ADMIN_GROUPS.map(group => ({ ...group, links: group.links.filter(link => role === "owner" || (manager && link.href !== "/admin/staff") || (!link.ownerOnly && (!link.permissions || link.permissions.some(p => permissions.includes(p))))) }))
    .filter(group => group.links.length > 0);
}

export function canManagePlatform(user?: { role?: string; staff_permissions?: string[] } | null) {
  return user?.role === "owner" || (["warehouse_staff", "cskh_staff"].includes(user?.role ?? "") && user?.staff_permissions?.includes("platform_manage") === true);
}

// Match the most specific visible route, including nested detail pages.
export function activeAdminHref(pathname: string, groups: ReturnType<typeof adminGroups>) {
  return groups.flatMap(group => group.links).filter(link => pathname === link.href || (link.href !== "/admin" && pathname.startsWith(`${link.href}/`)))
    .sort((a, b) => b.href.length - a.href.length)[0]?.href;
}
