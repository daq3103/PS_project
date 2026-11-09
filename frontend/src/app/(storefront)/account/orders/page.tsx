"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { api, type OrderOut } from "@/lib/api-client";
import { formatVnd } from "@/lib/format";

const STATUS: Record<string, string> = {
  pending: "Chờ xác nhận",
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
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(true);
  const [cancelling, setCancelling] = useState("");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  async function cancel(id: string) {
    setBusy(true); setError(""); setNotice("");
    try { await api.cancelOrder(id, reason.trim() || "Khách yêu cầu hủy"); setCancelling(""); setReason(""); await load(); setNotice("Đã hủy đơn hàng thành công."); }
    catch (e) { setError(e instanceof Error ? e.message : "Chưa hủy được đơn hàng."); }
    finally { setBusy(false); }
  }
  async function pay(id: string) {
    setBusy(true); setError("");
    try {
      const response = await api.getOrderPayment(id);
      if (response.checkout_url) window.location.assign(response.checkout_url);
      else setError("Liên kết thanh toán đang được chuẩn bị. Vui lòng thử lại sau ít phút.");
    } catch (e) { setError(e instanceof Error ? e.message : "Chưa mở được thanh toán."); }
    finally { setBusy(false); }
  }

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
      {notice && <p role="status" className="mt-4 rounded-xl bg-forest/10 p-3 text-sm text-forest">{notice}</p>}
      {loading && <p className="mt-6 text-ink-muted">Đang tải…</p>}
      {!loading && orders.length === 0 && (
        <p className="mt-6 text-ink-muted">
          Chưa có đơn.{" "}
          <Link href="/shop" className="text-forest underline">
            Mua sắm ngay
          </Link>
        </p>
      )}

      <ul className="mt-8 divide-y divide-line border-y border-line text-sm">
        {orders.map((o) => (
          <li key={o.id} className="py-4">
            <p className="font-mono font-medium">{o.order_code}</p>
            <p className="text-ink-muted">
              {STATUS[o.status] ?? "Đang xử lý"} · {o.payment_method === "cod" ? "Trả khi nhận hàng" : "Thanh toán online"} · {formatVnd(o.total_amount)}
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
            <div className="mt-3 flex flex-wrap gap-4">
              <Link href="/account/support" className="text-forest hover:underline">Cần hỗ trợ / đổi trả</Link>
              {o.status === "pending" && o.payment_method !== "cod" && <button disabled={busy} onClick={() => void pay(o.id)} className="text-forest hover:underline">Tiếp tục thanh toán</button>}
              {["pending", "confirmed", "packed"].includes(o.status) && <button disabled={busy} onClick={() => {setCancelling(o.id); setReason("");}} className="text-danger hover:underline">Yêu cầu hủy đơn</button>}
            </div>
            {cancelling === o.id && <div className="mt-3 space-y-3 rounded-xl border border-line p-4"><p>{o.payment_status === "paid" ? "Đơn đã thanh toán sẽ được chuyển sang kiểm tra hoàn tiền sau khi hủy." : "Đơn chưa thanh toán; hủy đơn sẽ dừng xử lý và giải phóng hàng đã giữ."}</p><label className="block">Lý do hủy<input value={reason} maxLength={1000} onChange={e => setReason(e.target.value)} className="mt-1 block w-full rounded-lg border border-line p-2" /></label><div className="flex gap-4"><button disabled={busy} onClick={() => void cancel(o.id)} className="rounded-full bg-danger px-4 py-2 text-white">Xác nhận hủy đơn</button><button onClick={() => setCancelling("")}>Giữ đơn hàng</button></div></div>}
          </li>
        ))}
      </ul>
    </div>
  );
}
