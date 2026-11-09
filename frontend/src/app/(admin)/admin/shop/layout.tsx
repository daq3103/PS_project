"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export default function ShopLayout({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  return <div className="space-y-5"><nav aria-label="Các trang Shop" className="flex gap-1 overflow-x-auto border-b border-line">
    {[["/admin/shop", "Tổng quan"], ["/admin/shop/insights", "Biểu đồ & chi phí"]].map(([href, label]) => {
      const active = path === href;
      return <Link key={href} href={href} aria-current={active ? "page" : undefined} className={`min-h-11 whitespace-nowrap rounded-t-lg border-b-2 px-5 py-3 text-sm font-medium transition focus-visible:outline-2 focus-visible:outline-forest ${active ? "border-forest bg-forest/10 text-forest" : "border-transparent text-ink-muted hover:bg-forest/5 hover:text-forest"}`}>{label}</Link>;
    })}
  </nav>{children}</div>;
}
