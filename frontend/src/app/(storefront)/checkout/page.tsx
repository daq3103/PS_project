"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { api, type CheckoutResponse, type CheckoutQuote } from "@/lib/api-client";
import { formatVnd } from "@/lib/format";
import { contactPhoneError } from "@/lib/phone";

function newIdempotencyKey(): string {
  if (typeof window !== "undefined") {
    const pending = sessionStorage.getItem("pethome_pending_checkout");
    if (pending) return pending;
  }
  if (typeof crypto !== "undefined" && crypto.randomUUID) return crypto.randomUUID();
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export default function CheckoutPage() {
  const router = useRouter();
  const [idempotencyKey] = useState(newIdempotencyKey);
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [address, setAddress] = useState("");
  const [paymentMethod, setPaymentMethod] = useState<"cod" | "vietqr">("cod");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [phoneError, setPhoneError] = useState("");
  const [result, setResult] = useState<CheckoutResponse | null>(null);
  const [quote, setQuote] = useState<CheckoutQuote | null>(null);
  const [promo, setPromo] = useState("");
  const [onlineAvailable, setOnlineAvailable] = useState(false);
  const [paymentUrl, setPaymentUrl] = useState("");
  useEffect(() => {
    const pending = sessionStorage.getItem("pethome_pending_checkout");
    if (pending) api.recoverCheckout(pending).then(order => {
      setResult(order);
      window.dispatchEvent(new CustomEvent("petshop:cart", { detail: { item_count: 0 } }));
      sessionStorage.removeItem("pethome_pending_checkout");
      sessionStorage.setItem("pethome_latest_order_id", order.id);
    }).catch(() => {});
  }, []);

  useEffect(() => { api.checkoutMethods().then(r => setOnlineAvailable(r.methods.some(m => m.id === "vietqr" && m.available))).catch(() => {}); }, []);
  useEffect(() => {
    if (!result || result.payment_method !== "vietqr") return;
    let stopped = false;
    let timer: ReturnType<typeof setTimeout>;
    let attempts = 0;
    async function check() {
      try {
        const response = await api.getOrderPayment(result!.id);
        if (stopped) return;
        if (response.checkout_url) { setPaymentUrl(response.checkout_url); return; }
      } catch { /* A durable job retries independently; the customer can refresh this screen. */ }
      if (!stopped && ++attempts < 20) timer = setTimeout(check, 3000);
    }
    void check();
    return () => { stopped = true; clearTimeout(timer); };
  }, [result]);

  useEffect(() => {
    void (async () => {
      try {
        const me = await api.me();
        if (!me.user) { router.replace("/login?next=%2Fcheckout"); return; }
        const addrs = await api.listAddresses();
        const d = addrs.find((a) => a.is_default) ?? addrs[0];
        if (!d) return;
        setName(d.recipient_name);
        setPhone(d.recipient_phone);
        setAddress(d.full_address || [d.street_address, d.ward_name, d.district_name, d.province_name].filter(Boolean).join(", "));
      } catch {
        router.replace("/login?next=%2Fcheckout");
      }
    })();
  }, [router]);

  const canSubmit = useMemo(
    () => name.trim() && phone.trim() && address.trim().length >= 10,
    [name, phone, address],
  );

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!canSubmit) return;
    const invalidPhone = contactPhoneError(phone);
    setPhoneError(invalidPhone);
    if (invalidPhone) return;
    setLoading(true);
    setError("");
    try {
      const me = await api.me();
      if (!me.user) { router.push("/login?next=%2Fcheckout"); return; }
      const body = {
        idempotency_key: idempotencyKey,
        customer_name: name.trim(),
        customer_phone: phone.trim(),
        shipping_address: { full_address: address.trim() },
        payment_method: paymentMethod,
        promo_code: promo.trim() || undefined,
      };
      if (!quote) {
        setQuote(await api.quoteCheckout(body));
        return;
      }
      sessionStorage.setItem("pethome_pending_checkout", idempotencyKey);
      const out = await api.checkout({...body, quote_id: quote.quote_id});
      sessionStorage.removeItem("pethome_pending_checkout");
      sessionStorage.setItem("pethome_latest_order_id", out.id);
      setResult(out);
      window.dispatchEvent(new CustomEvent("petshop:cart", { detail: { item_count: 0 } }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không đặt được đơn");
      setQuote(null);
    } finally {
      setLoading(false);
    }
  }

  if (result) {
    return (
      <div className="mx-auto max-w-lg">
        <h1 className="font-display text-3xl text-forest">Đặt hàng thành công</h1>
        <p className="mt-3 text-ink-muted">
          Mã đơn:{" "}
          <strong className="font-mono text-lg text-ink">{result.order_code}</strong>
        </p>
        <p className="mt-1 text-sm text-ink-muted">
          Thanh toán {result.payment_method === "vietqr" ? "VietQR" : "COD"}:{" "}
          {result.payment_status === "paid" ? "Đã thanh toán" : "Chờ xác nhận"}
        </p>
        <p className="mt-1 text-sm font-medium text-ink">{formatVnd(result.total_amount)}</p>
        {result.payment_method === "vietqr" && (paymentUrl ? <a href={paymentUrl} className="mt-5 inline-block rounded-full bg-forest px-5 py-3 text-white">Mở trang thanh toán an toàn</a> : <p className="mt-4 text-sm text-ink-muted">Đang chuẩn bị liên kết thanh toán. Bạn có thể xem lại trong phần theo dõi đơn.</p>)}
        {result.payment_method === "vietqr" && result.qr_code_url && (
          <div className="mt-6 border border-line bg-surface p-4">
            <p className="text-sm font-medium text-forest">Quét mã VietQR để thanh toán</p>
            <img
              src={result.qr_code_url}
              alt="Mã QR VietQR"
              className="mx-auto mt-4 max-h-64 w-auto"
            />
            {result.reservation_expires_at && (
              <p className="mt-3 text-center text-xs text-ink-muted">
                Giữ chỗ đến {new Date(result.reservation_expires_at).toLocaleString("vi-VN")}
              </p>
            )}
          </div>
        )}
        <div className="mt-8 flex flex-wrap gap-3 text-sm">
          <Link
            href={result.tracking_token ? `/track-order#token=${encodeURIComponent(result.tracking_token)}` : `/track-order?order_code=${encodeURIComponent(result.order_code)}&phone=${encodeURIComponent(phone)}`}
            className="rounded-full bg-forest px-4 py-2 font-medium text-white hover:bg-forest-deep"
          >
            Theo dõi đơn
          </Link>
          <Link href="/" className="rounded-full px-4 py-2 text-moss hover:underline">
            Về trang chủ
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-lg">
      <h1 className="font-display text-3xl">Thanh toán</h1>
      <p className="mt-2 text-sm text-ink-muted">
        Kiểm tra thông tin nhận hàng trước khi đặt.{" "}
        <Link href="/cart" className="text-moss hover:underline">
          Quay lại giỏ
        </Link>
      </p>

      <form onSubmit={onSubmit} onChange={() => setQuote(null)} className="mt-8 space-y-4">
        <fieldset disabled={loading} className="space-y-4">
        <Field label="Họ tên" value={name} onChange={setName} required />
        <Field label="Số điện thoại" value={phone} onChange={value => { setPhone(value); setPhoneError(""); }} required type="tel" error={phoneError} />
        <Field label="Địa chỉ nhận hàng (số nhà, đường, phường/xã, tỉnh/thành phố)" value={address} onChange={setAddress} required />
        <Field label="Mã giảm giá (nếu có)" value={promo} onChange={setPromo} />

        <fieldset className="space-y-2 text-sm">
          <legend className="text-ink-muted">Hình thức thanh toán</legend>
          <label className="flex cursor-pointer items-center gap-2">
            <input
              type="radio"
              name="payment"
              checked={paymentMethod === "cod"}
              onChange={() => setPaymentMethod("cod")}
            />
            COD — thanh toán khi nhận hàng
          </label>
          {onlineAvailable && <label className="flex cursor-pointer items-center gap-2">
            <input
              type="radio"
              name="payment"
              checked={paymentMethod === "vietqr"}
              onChange={() => setPaymentMethod("vietqr")}
            />
            Thanh toán online qua payOS
          </label>}
        </fieldset>

        {error && <p className="text-sm text-danger">{error}</p>}
        {quote && <section aria-label="Chi tiết thanh toán" className="space-y-2 rounded-2xl border border-line bg-paper p-4 text-sm" aria-live="polite">
          <p className="flex justify-between"><span>Tiền hàng</span><span>{formatVnd(quote.subtotal_amount)}</span></p>
          <p className="flex justify-between"><span>Giảm giá</span><span>−{formatVnd(quote.discount_amount)}</span></p>
          <p className="flex justify-between"><span>Phí giao hàng</span><span>{formatVnd(quote.shipping_fee - quote.shipping_discount)}</span></p>
          <p className="flex justify-between border-t border-line pt-3 text-base font-semibold text-forest"><span>Tổng thanh toán</span><span>{formatVnd(quote.total_amount)}</span></p>
          <p className="text-xs text-ink-muted">Báo giá có hiệu lực đến {new Date(quote.expires_at).toLocaleTimeString("vi-VN")}. Hàng được giữ sau khi đặt thành công.</p>
        </section>}

        <button
          type="submit"
          disabled={loading || !canSubmit}
          className="w-full rounded-full bg-forest py-2.5 text-sm font-medium text-white hover:bg-forest-deep disabled:opacity-60"
        >
          {loading ? "Đang xử lý…" : quote ? "Xác nhận đặt hàng" : "Kiểm tra tổng tiền"}
        </button>
        </fieldset>
      </form>
    </div>
  );
}

function Field({
  label,
  value,
  onChange,
  type = "text",
  required,
  error,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  type?: string;
  required?: boolean;
  error?: string;
}) {
  return (
    <label className="block text-sm">
      <span className="text-ink-muted">{label}</span>
      <input
        type={type}
        value={value}
        required={required}
        aria-invalid={!!error}
        onChange={(e) => onChange(e.target.value)}
        className="mt-1 w-full rounded-sm border border-line bg-surface px-3 py-2 outline-none focus:border-moss"
      />
      {error && <span role="alert" className="mt-1 block text-danger">{error}</span>}
    </label>
  );
}
