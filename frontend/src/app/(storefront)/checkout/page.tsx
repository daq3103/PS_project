"use client";

import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { api, type CheckoutResponse } from "@/lib/api-client";
import { formatVnd } from "@/lib/format";

function newIdempotencyKey(): string {
  if (typeof crypto !== "undefined" && crypto.randomUUID) return crypto.randomUUID();
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export default function CheckoutPage() {
  const [idempotencyKey] = useState(newIdempotencyKey);
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [province, setProvince] = useState("");
  const [district, setDistrict] = useState("");
  const [ward, setWard] = useState("");
  const [street, setStreet] = useState("");
  const [paymentMethod, setPaymentMethod] = useState<"cod" | "vietqr">("cod");
  const [note, setNote] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<CheckoutResponse | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        const me = await api.me();
        if (!me.user) return;
        const addrs = await api.listAddresses();
        const d = addrs.find((a) => a.is_default) ?? addrs[0];
        if (!d) return;
        setName(d.recipient_name);
        setPhone(d.recipient_phone);
        setProvince(d.province_name);
        setDistrict(d.district_name);
        setWard(d.ward_name);
        setStreet(d.street_address);
      } catch {
        /* guest or empty address book */
      }
    })();
  }, []);

  const canSubmit = useMemo(
    () => name.trim() && phone.trim() && province.trim() && district.trim() && ward.trim() && street.trim(),
    [name, phone, province, district, ward, street],
  );

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!canSubmit) return;
    setLoading(true);
    setError("");
    try {
      await api.me();
      const out = await api.checkout({
        idempotency_key: idempotencyKey,
        customer_name: name.trim(),
        customer_phone: phone.trim(),
        customer_email: email.trim() || undefined,
        shipping_address: {
          province: province.trim(),
          district: district.trim(),
          ward: ward.trim(),
          street: street.trim(),
        },
        payment_method: paymentMethod,
        customer_note: note.trim() || undefined,
      });
      setResult(out);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không đặt được đơn");
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
          {result.payment_status}
        </p>
        <p className="mt-1 text-sm font-medium text-ink">{formatVnd(result.total_amount)}</p>
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
            href={`/track-order?order_code=${encodeURIComponent(result.order_code)}&phone=${encodeURIComponent(phone)}`}
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
        Guest checkout — không cần đăng nhập.{" "}
        <Link href="/cart" className="text-moss hover:underline">
          Quay lại giỏ
        </Link>
      </p>

      <form onSubmit={onSubmit} className="mt-8 space-y-4">
        <Field label="Họ tên" value={name} onChange={setName} required />
        <Field label="Số điện thoại" value={phone} onChange={setPhone} required />
        <Field label="Email (tuỳ chọn)" value={email} onChange={setEmail} type="email" />
        <Field label="Tỉnh / Thành phố" value={province} onChange={setProvince} required />
        <Field label="Quận / Huyện" value={district} onChange={setDistrict} required />
        <Field label="Phường / Xã" value={ward} onChange={setWard} required />
        <Field label="Địa chỉ (số nhà, đường)" value={street} onChange={setStreet} required />

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
          <label className="flex cursor-pointer items-center gap-2">
            <input
              type="radio"
              name="payment"
              checked={paymentMethod === "vietqr"}
              onChange={() => setPaymentMethod("vietqr")}
            />
            VietQR — chuyển khoản ngay
          </label>
        </fieldset>

        <label className="block text-sm">
          <span className="text-ink-muted">Ghi chú</span>
          <textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            rows={2}
            className="mt-1 w-full rounded-sm border border-line bg-surface px-3 py-2 outline-none focus:border-moss"
          />
        </label>

        {error && <p className="text-sm text-danger">{error}</p>}

        <button
          type="submit"
          disabled={loading || !canSubmit}
          className="w-full rounded-full bg-forest py-2.5 text-sm font-medium text-white hover:bg-forest-deep disabled:opacity-60"
        >
          {loading ? "Đang xử lý…" : "Xác nhận đặt hàng"}
        </button>
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
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  type?: string;
  required?: boolean;
}) {
  return (
    <label className="block text-sm">
      <span className="text-ink-muted">{label}</span>
      <input
        type={type}
        value={value}
        required={required}
        onChange={(e) => onChange(e.target.value)}
        className="mt-1 w-full rounded-sm border border-line bg-surface px-3 py-2 outline-none focus:border-moss"
      />
    </label>
  );
}
