"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { api, type AddressOut } from "@/lib/api-client";

export default function AccountAddressesPage() {
  const router = useRouter();
  const [addresses, setAddresses] = useState<AddressOut[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const [recipientName, setRecipientName] = useState("");
  const [recipientPhone, setRecipientPhone] = useState("");
  const [provinceName, setProvinceName] = useState("Hà Nội");
  const [districtName, setDistrictName] = useState("");
  const [wardName, setWardName] = useState("");
  const [street, setStreet] = useState("");
  const [isDefault, setIsDefault] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const me = await api.me();
      if (!me.user) {
        router.replace("/login");
        return;
      }
      setAddresses(await api.listAddresses());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Không tải được địa chỉ");
    } finally {
      setLoading(false);
    }
  }, [router]);

  useEffect(() => {
    void load();
  }, [load]);

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError("");
    try {
      await api.createAddress({
        recipient_name: recipientName.trim(),
        recipient_phone: recipientPhone.trim(),
        province_id: 1,
        province_name: provinceName.trim(),
        district_id: 1,
        district_name: districtName.trim(),
        ward_code: "1",
        ward_name: wardName.trim(),
        street_address: street.trim(),
        is_default: isDefault,
      });
      setRecipientName("");
      setRecipientPhone("");
      setDistrictName("");
      setWardName("");
      setStreet("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Lưu địa chỉ thất bại");
    } finally {
      setSaving(false);
    }
  }

  async function makeDefault(id: string) {
    try {
      await api.updateAddress(id, { is_default: true });
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Không đặt mặc định được");
    }
  }

  async function remove(id: string) {
    try {
      await api.deleteAddress(id);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Xoá thất bại");
    }
  }

  return (
    <div>
      <div className="flex items-baseline justify-between gap-4">
        <h1 className="font-display text-3xl">Sổ địa chỉ</h1>
        <Link href="/account" className="text-sm text-moss hover:underline">
          ← Tài khoản
        </Link>
      </div>

      <form onSubmit={onCreate} className="mt-8 grid max-w-xl gap-3 sm:grid-cols-2">
        <Field label="Người nhận" value={recipientName} onChange={setRecipientName} required />
        <Field label="SĐT" value={recipientPhone} onChange={setRecipientPhone} required />
        <Field label="Tỉnh / TP" value={provinceName} onChange={setProvinceName} required />
        <Field label="Quận / Huyện" value={districtName} onChange={setDistrictName} required />
        <Field label="Phường / Xã" value={wardName} onChange={setWardName} required />
        <Field label="Địa chỉ" value={street} onChange={setStreet} required />
        <label className="flex items-center gap-2 text-sm sm:col-span-2">
          <input
            type="checkbox"
            checked={isDefault}
            onChange={(e) => setIsDefault(e.target.checked)}
          />
          Đặt làm mặc định
        </label>
        <div className="sm:col-span-2">
          <button
            type="submit"
            disabled={saving}
            className="rounded-full bg-forest px-5 py-2 text-sm font-medium text-white hover:bg-forest-deep disabled:opacity-60"
          >
            {saving ? "Đang lưu…" : "Thêm địa chỉ"}
          </button>
        </div>
      </form>

      {error && <p className="mt-4 text-sm text-danger">{error}</p>}
      {loading && <p className="mt-6 text-ink-muted">Đang tải…</p>}

      <ul className="mt-10 divide-y divide-line border-y border-line text-sm">
        {addresses.map((a) => (
          <li key={a.id} className="flex flex-wrap items-start justify-between gap-3 py-4">
            <div>
              <p className="font-medium">
                {a.recipient_name} · {a.recipient_phone}
                {a.is_default ? (
                  <span className="ml-2 text-xs font-normal text-forest">(mặc định)</span>
                ) : null}
              </p>
              <p className="text-ink-muted">
                {a.street_address}, {a.ward_name}, {a.district_name}, {a.province_name}
              </p>
            </div>
            <div className="flex gap-2">
              {!a.is_default && (
                <button
                  type="button"
                  className="text-forest hover:underline"
                  onClick={() => void makeDefault(a.id)}
                >
                  Đặt mặc định
                </button>
              )}
              <button
                type="button"
                className="text-danger hover:underline"
                onClick={() => void remove(a.id)}
              >
                Xoá
              </button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

function Field({
  label,
  value,
  onChange,
  required,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  required?: boolean;
}) {
  return (
    <label className="block text-sm">
      <span className="text-ink-muted">{label}</span>
      <input
        value={value}
        required={required}
        onChange={(e) => onChange(e.target.value)}
        className="mt-1 w-full rounded-sm border border-line bg-surface px-3 py-2 outline-none focus:border-forest"
      />
    </label>
  );
}
