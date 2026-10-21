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
    <div className="mx-auto max-w-lg">
      <h1 className="font-display text-4xl text-ink">Tài khoản</h1>
      <p className="mt-3 text-ink-muted">Xin chào, {user.full_name}</p>
      <ul className="mt-10 space-y-4 border-y border-line py-6 text-sm">
        <li><Link href="/account/community" className="font-semibold text-forest hover:underline">Tin cứu hộ và thông báo</Link></li>
        <li><Link href="/account/adoption-requests" className="font-semibold text-forest hover:underline">Hồ sơ nhận nuôi</Link></li>
        <li>
          <Link href="/account/profile" className="font-semibold text-forest hover:underline">
            Hồ sơ cá nhân
          </Link>
          <p className="mt-1 text-ink-muted">Thay đổi họ tên, SĐT.</p>
        </li>
        <li>
          <Link href="/account/orders" className="font-semibold text-forest hover:underline">
            Lịch sử đơn hàng
          </Link>
          <p className="mt-1 text-ink-muted">Xem đơn đã đặt và trạng thái.</p>
        </li>
        <li>
          <Link href="/account/addresses" className="font-semibold text-forest hover:underline">
            Sổ địa chỉ
          </Link>
          <p className="mt-1 text-ink-muted">Thêm, sửa địa chỉ giao hàng mặc định.</p>
        </li>
      </ul>
    </div>
  );
}
