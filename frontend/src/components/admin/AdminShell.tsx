"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { api, type UserDto } from "@/lib/api-client";
import { TotpProvider } from "./TotpProvider";

const ALL_NAV = [
  { href: "/admin", label: "Tổng quan" },
  { href: "/admin/orders", label: "Đơn hàng" },
  { href: "/admin/inventory-lots", label: "Lô hàng" },
  { href: "/admin/products", label: "Sản phẩm" },
  { href: "/admin/community", label: "Trạm cứu hộ" },
  { href: "/admin/promotions", label: "Khuyến mãi" },
  { href: "/admin/reviews", label: "Đánh giá" },
  { href: "/admin/reports", label: "Báo cáo" },
  { href: "/admin/analytics", label: "Truy cập & hiệu năng" },
  { href: "/admin/settings", label: "Cài đặt" },
];

const ROLE_LABELS: Record<string, string> = {
  owner: "Chủ shop",
  warehouse_staff: "Nhân viên kho",
  cskh_staff: "Nhân viên CSKH",
};

function allowedNav(role?: string) {
  switch (role) {
    case "owner":
      return ALL_NAV;
    case "warehouse_staff":
      return ALL_NAV.filter((n) =>
        ["/admin", "/admin/orders", "/admin/inventory-lots", "/admin/reports"].includes(n.href),
      );
    case "cskh_staff":
      return ALL_NAV.filter((n) =>
        ["/admin", "/admin/orders", "/admin/community", "/admin/reviews"].includes(n.href),
      );
    default:
      return ALL_NAV;
  }
}

export function AdminShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [user, setUser] = useState<UserDto | null>(null);
  const [loading, setLoading] = useState(true);
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    setLoading(true);
    api
      .me()
      .then((res) => {
        setUser(res.user);
      })
      .catch(() => setUser(null))
      .finally(() => setLoading(false));
  }, []);

  async function logout() {
    try {
      await api.logout();
    } finally {
      window.location.href = "/login";
    }
  }

  const nav = allowedNav(user?.role);

  return (
    <TotpProvider>
      <div className="flex min-h-screen">
        {/* Sidebar desktop */}
        <aside className="hidden w-56 shrink-0 flex-col border-r border-line bg-surface md:flex">
          <div className="flex items-center gap-3 border-b border-line px-5 py-4">
            <span className="font-display text-xl text-forest">Petshop Admin</span>
          </div>
          <nav className="flex-1 space-y-1 p-3">
            {nav.map((item) => {
              const active = pathname === item.href || (item.href !== "/admin" && pathname.startsWith(`${item.href}/`));
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`block rounded-sm px-3 py-2 text-sm transition ${
                    active
                      ? "bg-forest/10 font-medium text-forest"
                      : "text-ink-muted hover:bg-forest/5 hover:text-forest"
                  }`}
                >
                  {item.label}
                </Link>
              );
            })}
          </nav>
          <div className="border-t border-line p-4 text-xs text-ink-muted">
            {loading ? (
              "Đang tải…"
            ) : user ? (
              <div className="space-y-1">
                <p className="font-medium text-ink">{user.full_name}</p>
                <p>{user.email ?? user.phone}</p>
                <p className="rounded-full bg-forest/10 px-2 py-0.5 text-center font-medium text-forest">
                  {ROLE_LABELS[user.role] ?? user.role}
                </p>
                <button
                  type="button"
                  onClick={logout}
                  className="mt-2 text-left text-danger hover:underline"
                >
                  Đăng xuất
                </button>
              </div>
            ) : (
              <Link href="/login" className="text-forest hover:underline">
                Đăng nhập
              </Link>
            )}
          </div>
        </aside>

        {/* Mobile topbar */}
        <div className="flex min-w-0 flex-1 flex-col">
          <header className="sticky top-0 z-30 flex items-center justify-between border-b border-line bg-paper/90 px-4 py-3 backdrop-blur md:hidden">
            <span className="font-display text-lg text-forest">Petshop Admin</span>
            <button
              type="button"
              onClick={() => setMobileOpen((v) => !v)}
              className="rounded-sm border border-line px-3 py-1 text-sm"
            >
              {mobileOpen ? "Đóng" : "Menu"}
            </button>
          </header>
          {mobileOpen && (
            <nav className="border-b border-line bg-surface px-4 py-3 md:hidden">
              {nav.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={() => setMobileOpen(false)}
                  className="block py-2 text-sm text-ink-muted hover:text-forest"
                >
                  {item.label}
                </Link>
              ))}
            </nav>
          )}

          <main className="min-w-0 flex-1 p-4 md:p-6">{children}</main>
        </div>
      </div>
    </TotpProvider>
  );
}
