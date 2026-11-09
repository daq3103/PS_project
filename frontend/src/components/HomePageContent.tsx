"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api-client";
import { BRAND } from "@/lib/brand";

export default function HomePage() {
  const [rescueEnabled, setRescueEnabled] = useState<boolean | null>(null);
  useEffect(() => {
    void api.communityConfig().then(config => setRescueEnabled(config.enabled)).catch(() => setRescueEnabled(false));
  }, []);
  return <div className="space-y-8 md:space-y-12">
    <section className="grid items-center gap-7 md:grid-cols-2 md:gap-12">
      <div>
        <p className="text-sm font-semibold uppercase tracking-widest text-moss">Cùng {BRAND.name}</p>
        <h1 className="mt-4 font-display text-4xl leading-tight text-forest md:text-5xl">Một nơi dành cho<br />những người yêu thú cưng.</h1>
        <p className="mt-5 max-w-lg text-base leading-relaxed text-ink-muted">Chăm sóc người bạn nhỏ mỗi ngày, giúp bé tìm đường về nhà, hoặc mở lòng đón thêm một thành viên mới.</p>
      </div>
      <div className="relative aspect-[16/10] overflow-hidden rounded-3xl bg-surface">
        <Image src="/brand/hero-pets.jpg" alt="Những người bạn nhỏ" fill priority sizes="(max-width: 768px) 100vw, 560px" className="object-cover" />
      </div>
    </section>
    <section aria-label="Khám phá nền tảng" className="grid gap-5 md:grid-cols-2">
      <article className="flex flex-col rounded-3xl border border-line bg-surface p-6 md:p-8">
        <p className="text-sm font-medium text-moss">Kết nối những mái ấm</p>
        <h2 className="mt-2 font-display text-3xl text-forest">Trạm cứu hộ</h2>
        <p className="mt-3 flex-1 leading-relaxed text-ink-muted">Cùng tìm thú cưng thất lạc, giúp bé tìm lại chủ và kết nối những bé đang chờ một gia đình yêu thương.</p>
        {rescueEnabled ? <>
          <Link href="/tram-cuu-ho" className="mt-6 w-fit rounded-full bg-forest px-6 py-3 text-sm font-semibold text-white hover:bg-forest-deep">Khám phá Trạm cứu hộ <span aria-hidden="true">↗</span></Link>
          <div className="mt-5 flex flex-wrap gap-x-5 gap-y-2 text-sm text-forest">
            <Link href="/tram-cuu-ho?post_type=lost_pet" className="hover:underline">Thú cưng thất lạc</Link>
            <Link href="/tram-cuu-ho?post_type=found_pet" className="hover:underline">Tìm chủ</Link>
            <Link href="/tram-cuu-ho?post_type=adoption" className="hover:underline">Nhận nuôi</Link>
          </div>
        </> : <p role="status" className="mt-6 text-sm text-ink-muted">{rescueEnabled === null ? "Đang tải Trạm cứu hộ…" : "Trạm cứu hộ hiện chưa sẵn sàng. Bạn vui lòng quay lại sau."}</p>}
      </article>
      <article className="flex flex-col rounded-3xl border border-line bg-surface p-6 md:p-8">
        <p className="text-sm font-medium text-moss">Chăm sóc mỗi ngày</p>
        <h2 className="mt-2 font-display text-3xl text-forest">Shop</h2>
        <p className="mt-3 flex-1 leading-relaxed text-ink-muted">Tìm thức ăn, đồ dùng và phụ kiện phù hợp để thú cưng luôn khỏe mạnh, thoải mái bên bạn.</p>
        <Link href="/shop" className="mt-6 w-fit rounded-full bg-forest px-6 py-3 text-sm font-semibold text-white hover:bg-forest-deep">Khám phá Shop <span aria-hidden="true">↗</span></Link>
        <div className="mt-5 flex flex-wrap gap-x-5 gap-y-2 text-sm text-forest">
          <Link href="/c/thuc-an-hat" className="hover:underline">Thức ăn</Link>
          <Link href="/c/phu-kien" className="hover:underline">Phụ kiện</Link>
          <Link href="/track-order" className="hover:underline">Tra cứu đơn hàng</Link>
        </div>
      </article>
    </section>
    <p className="text-center text-sm text-ink-muted">Một tài khoản để mua sắm, đăng tin và kết nối cộng đồng.</p>
  </div>;
}
