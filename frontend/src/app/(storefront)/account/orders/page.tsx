"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { api, type OrderOut } from "@/lib/api-client";
import { formatVnd } from "@/lib/format";

const STATUS: Record<string, string> = {
  pending: "Chờ thanh toán",
  confirmed: "Đã xác nhận",
  packed: "Đã đóng gói",
  shipped: "Đang giao",
  delivered: "Đã giao",
  cancelled: "Đã huỷ",
};

export default function AccountOrdersPage() {
  const router = useRouter();
  const [orders, setOrders] = useState<OrderOut[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const me = await api.me();
      if (!me.user) {
        router.replace("/login");
        return;
      }
      setOrders(await api.listMyOrders({ limit: 50 }));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Không tải được đơn");
    } finally {
      setLoading(false);
    }
  }, [router]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div>
      <div className="flex items-baseline justify-between gap-4">
        <h1 className="font-display text-3xl">Đơn hàng của tôi</h1>
        <Link href="/account" className="text-sm text-moss hover:underline">
          ← Tài khoản
        </Link>
      </div>

      {error && <p className="mt-4 text-sm text-danger">{error}</p>}
      {loading && <p className="mt-6 text-ink-muted">Đang tải…</p>}
      {!loading && orders.length === 0 && (
        <p className="mt-6 text-ink-muted">
          Chưa có đơn.{" "}
          <Link href="/" className="text-forest underline">
            Mua sắm ngay
          </Link>
        </p>
      )}

      <ul className="mt-8 divide-y divide-line border-y border-line text-sm">
        {orders.map((o) => (
          <li key={o.id} className="py-4">
            <p className="font-mono font-medium">{o.order_code}</p>
            <p className="text-ink-muted">
              {STATUS[o.status] ?? o.status} · {o.payment_method} · {formatVnd(o.total_amount)}
            </p>
            <p className="text-xs text-ink-muted">
              {new Date(o.created_at).toLocaleString("vi-VN")}
            </p>
            <Link
              href={`/track-order?order_code=${encodeURIComponent(o.order_code)}&phone=${encodeURIComponent(o.customer_phone)}`}
              className="mt-2 inline-block text-forest hover:underline"
            >
              Theo dõi
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
