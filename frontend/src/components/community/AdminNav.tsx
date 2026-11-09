"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
export function CommunityAdminNav() {
  const path = usePathname();
  const links = [["/admin/community", "Tin cứu hộ"], ["/admin/community/new", "Đăng nhận nuôi"], ["/admin/community/adoptions", "Hồ sơ nhận nuôi"], ["/admin/community/reports", "Báo cáo vi phạm"], ["/admin/community/metrics", "Theo dõi vận hành"]];
  return <nav aria-label="Quản lý cứu hộ" className="mb-5 flex flex-wrap gap-2 text-sm">
    {links.map(([href, label]) => { const active = href === "/admin/community" ? path === href || path.startsWith("/admin/community/") && !links.some(([other]) => other !== href && path.startsWith(other)) : path === href || path.startsWith(`${href}/`); return <Link key={href} href={href} aria-current={active ? "page" : undefined} className={`inline-flex min-h-10 items-center rounded-full border px-4 py-2 font-medium transition focus-visible:outline-2 focus-visible:outline-forest ${active ? "border-forest bg-forest text-white" : "border-line text-forest hover:border-forest/40 hover:bg-forest/10"}`}>{label}</Link>; })}
  </nav>;
}
