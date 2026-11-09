"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { api, type UserDto } from "@/lib/api-client";
import { BRAND } from "@/lib/brand";
import { AdminUserContext } from "./AdminUserContext";
import { ADMIN_GROUPS, STAFF_PERMISSION_LABELS, activeAdminHref, adminGroups } from "@/lib/admin-navigation";

const ROLE_LABELS: Record<string, string> = {
  owner: "Quản trị viên",
  warehouse_staff: "Nhân viên kho",
  cskh_staff: "Nhân viên chăm sóc khách hàng",
};

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

  useEffect(() => {
    if (!loading && !user) {
      window.location.replace("/login?next=/admin");
      return;
    }
    if (user?.role === "owner" && user.totp_enabled === false && pathname !== "/admin/settings") {
      window.location.replace("/admin/settings");
    }
  }, [user, pathname, loading]);

  async function logout() {
    try {
      await api.logout();
    } finally {
      window.location.href = "/login";
    }
  }

  const groups = adminGroups(user?.role, user?.staff_permissions);
  const activeHref = activeAdminHref(pathname, ADMIN_GROUPS);
  const canViewPage = groups.some(group => group.links.some(link => link.href === activeHref));
  if (!loading && user && !groups.length) {
    return <main className="mx-auto max-w-xl p-8"><h1 className="text-2xl font-semibold">Bạn không có quyền truy cập quản trị.</h1><Link href="/account" className="mt-4 inline-block underline">Về tài khoản của tôi</Link></main>;
  }
  const navigation = groups.map(group => <details key={`${group.label}:${pathname}`} open={group.label === "Điều hành" || group.links.some(link => link.href === activeHref)} className="group mb-2 rounded-xl border border-transparent open:border-line open:bg-paper" >
    <summary className="flex cursor-pointer list-none items-center justify-between gap-2 rounded-lg px-3 py-3 text-sm font-semibold text-forest hover:bg-forest/5 [&::-webkit-details-marker]:hidden"><span>{group.label}</span><span aria-hidden="true" className="text-xs transition group-open:rotate-180">⌄</span></summary>
    <ul className="space-y-1 px-1 pb-2">{group.links.map(item => {
      const active = activeHref === item.href;
      return <li key={item.href}><Link href={item.href} onClick={() => setMobileOpen(false)} aria-current={active ? "page" : undefined}
        className={`block min-h-10 rounded-lg px-3 py-2.5 text-sm transition focus-visible:outline-2 focus-visible:outline-forest ${active ? "bg-forest font-semibold text-white" : "text-ink-muted hover:bg-forest/10 hover:text-forest"}`}>{item.label}</Link></li>;
    })}</ul>
  </details>);

  return (
    <AdminUserContext.Provider value={user}>
      <div className="flex min-h-screen">
        {/* Sidebar desktop */}
        <aside className="hidden w-64 shrink-0 flex-col overflow-hidden border-r border-line bg-surface md:sticky md:top-0 md:flex md:h-dvh md:self-start">
          <div className="flex shrink-0 items-center gap-3 border-b border-line px-5 py-4">
            <span className="font-display text-xl text-forest">{BRAND.name} · Quản trị</span>
          </div>
          <nav aria-label="Điều hướng quản trị" className="min-h-0 flex-1 overflow-y-auto p-3">{navigation}<Link href="/" className="block px-3 py-2 text-sm text-forest hover:underline">Xem website ↗</Link></nav>
          <div className="shrink-0 border-t border-line p-4 text-xs text-ink-muted">
            {loading ? (
              "Đang tải…"
            ) : user ? (
              <div className="space-y-1">
                <p className="font-medium text-ink">{user.full_name}</p>
                <p className="break-all">{user.email ?? user.phone}</p>
                <p className="rounded-full bg-forest/10 px-2 py-0.5 text-center font-medium text-forest">
                  {user.role === "owner" ? ROLE_LABELS.owner : "Nhân viên"}
                </p>
                {user.role !== "owner" && <p className="leading-relaxed">{user.staff_permissions?.map(p => STAFF_PERMISSION_LABELS[p]).filter(Boolean).join(" · ")}</p>}
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
            <span className="font-display text-lg text-forest">{BRAND.name} · Quản trị</span>
            <button
              type="button"
              onClick={() => setMobileOpen((v) => !v)}
              aria-expanded={mobileOpen}
              aria-controls="admin-mobile-navigation"
              className="rounded-sm border border-line px-3 py-1 text-sm"
            >
              {mobileOpen ? "Đóng" : "Menu"}
            </button>
          </header>
          {mobileOpen && (
            <nav id="admin-mobile-navigation" aria-label="Điều hướng quản trị" className="max-h-[75dvh] overflow-y-auto border-b border-line bg-surface px-4 py-3 md:hidden">{navigation}<Link href="/" className="block px-3 py-2 text-sm text-forest">Xem website ↗</Link><button onClick={logout} className="px-3 py-2 text-sm text-danger">Đăng xuất</button></nav>
          )}

          <main className="min-w-0 flex-1 p-4 md:p-6">{loading ? <p className="text-ink-muted" role="status">Đang tải khu vực làm việc…</p> : canViewPage ? children : <div className="max-w-xl rounded-2xl border border-line bg-surface p-6"><h1 className="font-display text-2xl text-forest">Bạn chưa được cấp quyền cho khu vực này</h1><p className="mt-3 text-sm text-ink-muted">Liên hệ quản trị viên nếu bạn cần nhận thêm công việc.</p><Link href="/admin" className="mt-5 inline-block text-sm font-medium text-forest underline">Về tổng quan</Link></div>}</main>
        </div>
      </div>
    </AdminUserContext.Provider>
  );
}
