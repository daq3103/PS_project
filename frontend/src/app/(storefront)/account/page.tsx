"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, type UserDto } from "@/lib/api-client";

export default function AccountPage() {
  const router = useRouter();
  const [user, setUser] = useState<UserDto | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    void (async () => {
      try {
        const me = await api.me();
        if (!me.user) {
          router.replace("/login");
          return;
        }
        setUser(me.user);
      } catch {
        setError("Không tải được tài khoản");
      }
    })();
  }, [router]);

  if (error) return <p className="text-danger">{error}</p>;
  if (!user) return <p className="text-ink-muted">Đang tải…</p>;

  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="font-display text-4xl text-ink">Tài khoản</h1>
      <p className="mt-3 text-ink-muted">Xin chào, {user.full_name}</p>
      <Link href="/account/profile" className="mt-5 inline-flex min-h-11 items-center rounded-full border border-forest/20 px-4 py-2 text-sm font-semibold text-forest transition hover:bg-forest/10">Hồ sơ cá nhân</Link>
      <div className="mt-8 grid gap-5 sm:grid-cols-2">
        <section className="rounded-2xl border border-line p-5">
          <h2 className="font-display text-2xl text-forest">Shop</h2>
          <ul className="mt-4 space-y-1 text-sm text-forest">
            <li><Link href="/account/orders" className="block rounded-lg px-3 py-3 transition hover:bg-forest/10">Lịch sử đơn hàng</Link></li>
            <li><Link href="/account/addresses" className="block rounded-lg px-3 py-3 transition hover:bg-forest/10">Địa chỉ giao hàng</Link></li>
            <li><Link href="/account/support" className="block rounded-lg px-3 py-3 transition hover:bg-forest/10">Yêu cầu hỗ trợ và đổi trả</Link></li>
          </ul>
        </section>
        <section className="rounded-2xl border border-line p-5">
          <h2 className="font-display text-2xl text-forest">Trạm cứu hộ</h2>
          <ul className="mt-4 space-y-1 text-sm text-forest">
            <li><Link href="/account/rescue" className="block rounded-lg px-3 py-3 transition hover:bg-forest/10">Lịch hẹn, đồng hành và phần việc của tôi</Link></li>
            <li><Link href="/account/community" className="block rounded-lg px-3 py-3 transition hover:bg-forest/10">Tin cứu hộ và thông báo</Link></li>
            <li><Link href="/account/adoption-requests" className="block rounded-lg px-3 py-3 transition hover:bg-forest/10">Hồ sơ nhận nuôi</Link></li>
          </ul>
        </section>
      </div>
    </div>
  );
}
