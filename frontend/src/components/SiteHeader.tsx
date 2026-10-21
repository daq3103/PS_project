"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useState } from "react";
import { api, type UserDto } from "@/lib/api-client";
import { UserMenu } from "./UserMenu";

const SHOP_LINKS = [
  { href: "/", label: "Khám phá shop" },
  { href: "/search", label: "Tìm sản phẩm" },
  { href: "/c/thuc-an-hat", label: "Thức ăn" },
  { href: "/c/phu-kien", label: "Phụ kiện" },
  { href: "/track-order", label: "Tra cứu đơn hàng" },
];
const RESCUE_TYPES = [["", "Tất cả tin"], ["lost_pet", "Thất lạc"], ["found_pet", "Tìm chủ"], ["adoption", "Nhận nuôi"]];

export function SiteHeader() {
  return <Suspense fallback={<div className="h-32 border-b border-line bg-paper" />}><HeaderContent /></Suspense>;
}

function HeaderContent() {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const query = searchParams.toString();
  const rescue = pathname.startsWith("/tram-cuu-ho") || pathname.startsWith("/account/community") || pathname.startsWith("/account/adoption-requests");
  const sharedAccount = ["/account", "/account/profile", "/account/addresses", "/login", "/register", "/forgot-password", "/reset-password"].includes(pathname);
  const [user, setUser] = useState<UserDto | null>(null);
  const [cartCount, setCartCount] = useState(0);
  const [ready, setReady] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [communityEnabled, setCommunityEnabled] = useState(true);

  const refreshSession = useCallback(async () => {
    try {
      const me = await api.me();
      setUser(me.user);
      try { setCartCount((await api.getCart()).item_count); } catch { setCartCount(0); }
    } catch { setUser(null); setCartCount(0); }
    finally { setReady(true); }
  }, []);

  useEffect(() => { void refreshSession(); }, [pathname, refreshSession]);
  useEffect(() => {
    void api.communityConfig().then(config => setCommunityEnabled(config.enabled)).catch(() => setCommunityEnabled(false));
  }, []);
  useEffect(() => {
    const onAuth = () => void refreshSession();
    window.addEventListener("petshop:auth", onAuth);
    return () => window.removeEventListener("petshop:auth", onAuth);
  }, [refreshSession]);
  useEffect(() => { setMenuOpen(false); }, [pathname, query]);

  const rescueLinks = RESCUE_TYPES.map(([type, label]) => {
    const params = new URLSearchParams(pathname === "/tram-cuu-ho" ? query : "");
    params.delete("cursor");
    if (type) params.set("post_type", type); else params.delete("post_type");
    return {
      href: `/tram-cuu-ho${params.size ? `?${params}` : ""}`, label,
      active: pathname === "/tram-cuu-ho" && (searchParams.get("post_type") ?? "") === type,
    };
  }).concat([
    { href: "/account/community", label: "Tin của tôi", active: pathname.startsWith("/account/community") },
    { href: "/account/adoption-requests", label: "Hồ sơ nhận nuôi", active: pathname.startsWith("/account/adoption-requests") },
  ]);
  const links = rescue ? rescueLinks : SHOP_LINKS.map(link => ({ ...link, active: pathname === link.href }));
  const sectorClass = (active: boolean) => `flex flex-1 items-center justify-center gap-2 whitespace-nowrap rounded-full px-5 py-2.5 text-sm font-semibold transition md:flex-none ${active ? "bg-forest text-white shadow-sm" : "text-ink-muted hover:bg-forest/10 hover:text-forest"}`;

  return (
    <header className="sticky top-0 z-40 border-b border-line bg-paper/95 backdrop-blur-md">
      <div className="mx-auto grid max-w-6xl grid-cols-[1fr_auto] items-center gap-x-4 gap-y-3 px-4 py-3 md:grid-cols-[1fr_auto_1fr] md:px-6">
        <Link href="/" aria-label="Petshop — Trang chủ" className="flex w-fit items-center gap-2.5">
          <Image src="/brand/brand-mark.jpg" alt="" width={36} height={36} className="h-9 w-9 rounded-full object-cover ring-1 ring-forest/20" />
          <span className="font-display text-xl font-semibold tracking-tight text-forest md:text-2xl">Petshop</span>
        </Link>
        <nav aria-label="Khu vực chính" className="col-span-2 row-start-2 flex rounded-full border border-line bg-surface p-1 md:col-span-1 md:col-start-2 md:row-start-1">
          <Link href="/" aria-current={!rescue && !sharedAccount ? "true" : undefined} className={sectorClass(!rescue && !sharedAccount)}><SectorIcon />Shop</Link>
          {communityEnabled && <Link href="/tram-cuu-ho" aria-current={rescue ? "true" : undefined} className={sectorClass(rescue)}><SectorIcon rescue />Trạm cứu hộ</Link>}
        </nav>
        <div className="col-start-2 row-start-1 flex min-w-0 items-center justify-end gap-2 md:col-start-3">
          {!ready ? <span className="h-9 w-24 animate-pulse rounded-full bg-forest/10" /> : user ? <UserMenu user={user} communityEnabled={communityEnabled} /> : <>
            <Link href="/register" className="hidden rounded-full px-3 py-2 text-sm font-medium text-forest lg:block">Đăng ký</Link>
            <Link href="/login" className="rounded-full border border-forest/30 px-4 py-2 text-sm font-semibold text-forest transition hover:bg-forest/10">Đăng nhập</Link>
          </>}
        </div>
      </div>
      <div className="border-t border-line/60 bg-surface/60">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-x-3 px-4 md:px-6">
          <button type="button" aria-expanded={menuOpen} aria-controls="section-navigation" onClick={() => setMenuOpen(v => !v)} className="flex items-center gap-2 py-3 text-sm font-medium text-forest lg:hidden">
            <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d={menuOpen ? "m6 6 12 12M6 18 18 6" : "M4 6h16M4 12h16M4 18h16"} /></svg>
            {rescue ? "Khám phá cứu hộ" : "Danh mục shop"}
          </button>
          <nav id="section-navigation" aria-label={rescue ? "Menu Trạm cứu hộ" : "Menu Shop"} onKeyDown={event => { if (event.key === "Escape") { setMenuOpen(false); document.querySelector<HTMLButtonElement>('[aria-controls="section-navigation"]')?.focus(); } }} className={`${menuOpen ? "flex" : "hidden"} order-3 w-full flex-col gap-1 border-t border-line py-2 text-sm lg:order-none lg:flex lg:w-auto lg:flex-row lg:border-0`}>
            {links.map(link => <Link key={link.label} href={link.href} onClick={() => setMenuOpen(false)} aria-current={link.active ? "page" : undefined} className={`rounded-full px-3 py-2 transition ${link.active ? "bg-forest/10 font-semibold text-forest" : "text-ink-muted hover:bg-forest/5 hover:text-forest"}`}>{link.label}</Link>)}
          </nav>
          {rescue ? <Link href="/tram-cuu-ho/dang-tin" className="my-2 rounded-full bg-forest px-4 py-2 text-sm font-semibold text-white transition hover:bg-forest-deep">Đăng tin</Link> : <Link href="/cart" className="my-2 rounded-full bg-forest px-4 py-2 text-sm font-semibold text-white transition hover:bg-forest-deep">Giỏ hàng{cartCount > 0 ? ` (${cartCount})` : ""}</Link>}
        </div>
      </div>
    </header>
  );
}

function SectorIcon({ rescue = false }: { rescue?: boolean }) {
  return <svg aria-hidden="true" className="h-4 w-4 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">{rescue ? <path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1.1-1.1a5.5 5.5 0 0 0-7.8 7.8L12 21l8.8-8.6a5.5 5.5 0 0 0 0-7.8Z" /> : <><path d="M3 9h18l-2-6H5L3 9ZM5 9v12h14V9M9 21v-7h6v7" /><path d="M3 9a3 3 0 0 0 6 0 3 3 0 0 0 6 0 3 3 0 0 0 6 0" /></>}</svg>;
}
