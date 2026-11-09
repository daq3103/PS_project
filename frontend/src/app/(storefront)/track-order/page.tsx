"use client";

import { FormEvent, Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { api, type TrackedOrderOut } from "@/lib/api-client";
import { formatVnd } from "@/lib/format";

const STATUS_LABEL: Record<string, string> = {
  pending: "Chờ xử lý",
  confirmed: "Đã xác nhận",
  packed: "Đã đóng gói",
  shipped: "Đang giao",
  delivered: "Đã giao",
  cancelled: "Đã huỷ",
};

const ORDER_STEPS = [
  { key: "pending", label: "Đặt hàng" },
  { key: "confirmed", label: "Xác nhận" },
  { key: "packed", label: "Đóng gói" },
  { key: "shipped", label: "Đang giao" },
  { key: "delivered", label: "Đã giao" },
];

export default function TrackOrderPage() {
  return (
    <Suspense fallback={<Loading />}>
      <TrackOrderForm />
    </Suspense>
  );
}

function Loading() {
  return (
    <div className="flex min-h-[70vh] items-center justify-center bg-[#dbe7e0]">
      <p className="text-ink-muted">Đang tải…</p>
    </div>
  );
}

function TrackOrderForm() {
  const searchParams = useSearchParams();
  const [orderCode, setOrderCode] = useState("");
  const [phone, setPhone] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [order, setOrder] = useState<TrackedOrderOut | null>(null);
  const [email, setEmail] = useState("");
  const [notice, setNotice] = useState("");
  async function resend(e: FormEvent) {
    e.preventDefault(); setLoading(true); setError(""); setNotice("");
    try { setNotice((await api.requestTrackingLink(orderCode.trim(), email.trim())).message); }
    catch (e) { setError(e instanceof Error ? e.message : "Chưa gửi được yêu cầu."); }
    finally { setLoading(false); }
  }

  useEffect(() => {
    const code = searchParams.get("order_code");
    const ph = searchParams.get("phone");
    if (code) setOrderCode(code);
    if (ph) setPhone(ph);
  }, [searchParams]);

  async function lookup(e?: FormEvent) {
    e?.preventDefault();
    if (!orderCode.trim() || !phone.trim()) {
      setOrder(null);
      setError(!orderCode.trim() ? "Vui lòng nhập mã đơn hàng." : "Vui lòng nhập số điện thoại đặt hàng.");
      return;
    }
    setLoading(true);
    setError("");
    setOrder(null);
    try {
      const data = await api.trackOrder(orderCode.trim(), phone.trim());
      setOrder(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không tra cứu được đơn");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    const token = new URLSearchParams(window.location.hash.slice(1)).get("token");
    const code = searchParams.get("order_code"), ph = searchParams.get("phone");
    if (token || (code && ph)) {
      setLoading(true);
      const request = token ? api.lookupOrder(token) : api.trackOrder(code!, ph!);
      request.then(setOrder).catch(err => setError(err instanceof Error ? err.message : "Không tra cứu được đơn")).finally(() => setLoading(false));
    } else {
      const lastOrder = sessionStorage.getItem("pethome_latest_order_id");
      if (lastOrder) {
        setLoading(true);
        api.getOrder(lastOrder).then(o => {
          setOrderCode(o.order_code); setPhone(o.customer_phone);
          return api.trackOrder(o.order_code, o.customer_phone);
        }).then(setOrder).catch(() => {}).finally(() => setLoading(false));
      }
    }
  }, [searchParams]);

  return (
    <div className="-mx-4 -my-8 flex min-h-[calc(100vh-4rem)] items-start justify-center bg-[#dbe7e0] px-4 py-10 md:-mx-6 md:-my-10 md:items-center md:py-16">
      <div className="w-full max-w-xl">
        <div className="rounded-sm border border-line bg-surface p-6 shadow-sm transition-shadow duration-200 hover:shadow-md md:p-10">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-forest/10 text-forest">
            <PackageIcon />
          </div>
          <h1 className="mt-4 text-center font-display text-3xl text-ink">
            Tra cứu đơn hàng
          </h1>
          <p className="mt-2 text-center text-sm text-ink/70">
            Mở liên kết trong email xác nhận, hoặc tra cứu trên thiết bị đã đặt hàng. Bạn cũng có thể đăng nhập để xem đơn của mình.
          </p>

          <form noValidate onSubmit={lookup} className="mt-8 space-y-4">
            <label className="block text-sm">
              <span className="font-medium text-ink">Mã đơn</span>
              <input
                value={orderCode}
                onChange={(e) => setOrderCode(e.target.value.toUpperCase())}
                required
                className="mt-1.5 w-full rounded-sm border border-line bg-surface px-3 py-2.5 font-mono uppercase outline-none transition duration-200 hover:border-forest/40 focus:border-forest"
                placeholder="VD: AB12CD34EF"
              />
            </label>
            <label className="block text-sm">
              <span className="font-medium text-ink">Số điện thoại đặt hàng</span>
              <input
                type="tel"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                required
                className="mt-1.5 w-full rounded-sm border border-line bg-surface px-3 py-2.5 outline-none transition duration-200 hover:border-forest/40 focus:border-forest"
                placeholder="VD: 0909123456"
              />
            </label>

            {error && (
              <p className="rounded-sm bg-danger/5 px-3 py-2 text-sm text-danger">
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full rounded-full bg-forest py-3 text-sm font-bold tracking-wide text-white shadow-sm transition duration-200 hover:-translate-y-0.5 hover:bg-forest-deep hover:shadow-md disabled:opacity-60 disabled:hover:translate-y-0"
            >
              {loading ? "Đang tra cứu…" : "Tra cứu"}
            </button>
          </form>
          <details className="mt-5 text-sm"><summary className="cursor-pointer text-forest">Cần liên kết tra cứu mới?</summary><form onSubmit={resend} className="mt-3 space-y-3"><p className="text-xs leading-6 text-ink-muted">Nhập mã đơn ở trên và email đã dùng khi đặt hàng. Liên kết mới chỉ được gửi tới email nhận đơn.</p><label className="block">Email nhận đơn<input type="email" required value={email} onChange={e => setEmail(e.target.value)} className="mt-1 block w-full rounded-lg border border-line bg-surface p-2" /></label><button disabled={loading || orderCode.trim().length < 6} className="rounded-full border border-forest px-4 py-2 text-forest disabled:opacity-40">Gửi liên kết mới</button></form></details>
          {notice && <p role="status" className="mt-3 text-sm text-forest">{notice}</p>}

          <div className="mt-5 flex items-center justify-between text-xs text-ink-muted">
            <span>Ví dụ: AB12CD34EF</span>
            <Link
              href="/account/orders"
              className="text-forest transition duration-200 hover:text-forest-deep hover:underline"
            >
              Xem đơn của tôi
            </Link>
          </div>
        </div>

        {order && (
          <div className="mt-6 rounded-sm border border-line bg-surface p-6 shadow-sm transition-shadow duration-200 hover:shadow-md md:p-10">
            <div className="flex items-center justify-between gap-4">
              <h2 className="font-display text-xl text-forest">Kết quả</h2>
              <span
                className={`shrink-0 rounded-full px-3 py-1 text-xs font-medium ${
                  order.status === "cancelled"
                    ? "bg-danger/10 text-danger"
                    : order.status === "delivered"
                      ? "bg-forest/10 text-forest"
                      : "bg-honey/10 text-honey"
                }`}
              >
                {STATUS_LABEL[order.status] ?? order.status}
              </span>
            </div>

            <Timeline status={order.status} />

            <dl className="mt-8 space-y-3 border-t border-line pt-6 text-sm">
              <Row label="Mã đơn" value={order.order_code} mono />
              <Row label="Thanh toán" value={({unpaid: "Chưa thanh toán", paid: "Đã thanh toán", underpaid: "Cần kiểm tra số tiền", overpaid: "Đã nhận tiền, cần đối chiếu khoản dư"} as Record<string, string>)[order.payment_status] ?? "Đang kiểm tra"} />
              <Row label="Người nhận" value={order.customer_name} />
              <Row label="SĐT" value={order.customer_phone_masked} />
              <Row
                label="Địa chỉ"
                value={order.shipping_address?.street_address || [
                  order.shipping_address?.street,
                  order.shipping_address?.ward,
                  order.shipping_address?.district,
                  order.shipping_address?.province,
                ]
                  .filter(Boolean)
                  .join(", ")}
              />
              <Row label="Tổng tiền" value={formatVnd(order.total_amount)} />
              <Row
                label="Ngày đặt"
                value={new Date(order.created_at).toLocaleString("vi-VN")}
              />
            </dl>

            {order.items?.length > 0 && (
              <div className="mt-6">
                <h3 className="text-sm font-medium text-ink">Sản phẩm</h3>
                <ul className="mt-3 divide-y divide-line border-y border-line text-sm">
                  {order.items.map((item, i) => (
                    <li
                      key={i}
                      className="flex justify-between gap-4 rounded px-2 py-3 -mx-2 transition duration-200 hover:bg-moss/[0.04]"
                    >
                      <span className="text-ink">
                        {item.product_name_snapshot}
                        {item.variant_title_snapshot
                          ? `, ${item.variant_title_snapshot}`
                          : ""}{" "}
                        × {item.qty}
                      </span>
                      <span className="shrink-0 text-ink-muted">
                        {formatVnd(item.line_total)}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function Timeline({ status }: { status: string }) {
  if (status === "cancelled") {
    return (
      <div className="mt-6 rounded-sm border border-danger/20 bg-danger/5 p-4">
        <p className="text-sm font-medium text-danger">Đơn hàng đã bị huỷ</p>
        <p className="mt-1 text-xs text-ink-muted">
          Nếu bạn đã thanh toán, vui lòng liên hệ hotline/zalo để được hỗ trợ hoàn tiền.
        </p>
      </div>
    );
  }

  const activeIndex = ORDER_STEPS.findIndex((s) => s.key === status);

  return (
    <div className="relative mt-8">
      <div className="absolute top-[11px] left-0 right-0 h-0.5 bg-line" />
      <div
        className="absolute top-[11px] left-0 h-0.5 bg-forest transition-all"
        style={{
          width: `${Math.max(0, Math.min(1, activeIndex / (ORDER_STEPS.length - 1))) * 100}%`,
        }}
      />
      <div className="relative flex justify-between">
        {ORDER_STEPS.map((step, i) => {
          const completed = i <= activeIndex;
          const current = i === activeIndex;
          return (
            <div key={step.key} className="group flex flex-col items-center">
              <div
                className={`flex h-6 w-6 items-center justify-center rounded-full border-2 text-[10px] font-bold transition-all duration-200 group-hover:scale-110 ${
                  completed
                    ? "border-forest bg-forest text-white"
                    : "border-line bg-surface text-ink-muted"
                } ${current ? "ring-4 ring-forest/10" : ""}`}
              >
                {completed ? (
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    viewBox="0 0 20 20"
                    fill="currentColor"
                    className="h-3.5 w-3.5"
                  >
                    <path
                      fillRule="evenodd"
                      d="M16.704 4.153a.75.75 0 0 1 .143 1.052l-8 10.5a.75.75 0 0 1-1.127.075l-4.5-4.5a.75.75 0 0 1 1.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 0 1 1.05-.143Z"
                      clipRule="evenodd"
                    />
                  </svg>
                ) : (
                  i + 1
                )}
              </div>
              <span
                className={`mt-2 text-center text-[10px] font-medium transition-colors duration-200 group-hover:text-forest ${
                  current ? "text-forest" : completed ? "text-ink" : "text-ink-muted"
                }`}
              >
                {step.label}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function Row({
  label,
  value,
  mono,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div className="group -mx-1 flex flex-wrap justify-between gap-2 rounded px-1 py-1 transition duration-200 hover:bg-moss/[0.04]">
      <dt className="text-ink-muted transition group-hover:text-ink">{label}</dt>
      <dd
        className={`max-w-[70%] text-right transition group-hover:text-forest ${
          mono ? "font-mono font-medium" : ""
        }`}
      >
        {value}
      </dd>
    </div>
  );
}

function PackageIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="h-6 w-6"
    >
      <path d="m7.5 4.27 9 5.15" />
      <path d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z" />
      <path d="m3.3 7 8.7 5 8.7-5" />
      <path d="M12 22V12" />
    </svg>
  );
}
