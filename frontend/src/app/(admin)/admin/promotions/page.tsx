"use client";

import { useCallback, useEffect, useState } from "react";
import { api, type PromotionOut } from "@/lib/api-client";
import { formatVnd } from "@/lib/format";
import { DataTable, type Column } from "@/components/admin/DataTable";
import { StatusBadge } from "@/components/admin/StatusBadge";

type DiscountType = "percentage" | "fixed_amount" | "free_shipping";

function formatPromoType(p: PromotionOut): string {
  if (p.discount_type === "percentage") return `${p.discount_value ?? "?"}%`;
  if (p.discount_type === "free_shipping") return "Free ship";
  if (p.discount_value != null) return formatVnd(p.discount_value);
  return p.discount_type;
}

export default function AdminPromotionsPage() {
  const [promos, setPromos] = useState<PromotionOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // create form
  const [code, setCode] = useState("");
  const [description, setDescription] = useState("");
  const [discountType, setDiscountType] = useState<DiscountType>("percentage");
  const [discountValue, setDiscountValue] = useState("10");
  const [minSubtotal, setMinSubtotal] = useState("0");
  const [usageLimit, setUsageLimit] = useState("");
  const [startsAt, setStartsAt] = useState("");
  const [expiresAt, setExpiresAt] = useState("");
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setPromos(await api.adminListPromotions());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Không tải được khuyến mãi");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function onCreate(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError("");
    try {
      await api.adminCreatePromotion({
        code: code.trim().toUpperCase(),
        description: description.trim() || undefined,
        discount_type: discountType,
        discount_value: Number(discountValue) || 0,
        min_order_subtotal: Number(minSubtotal) || 0,
        usage_limit: usageLimit ? Number(usageLimit) : null,
        starts_at: new Date(startsAt).toISOString(),
        expires_at: new Date(expiresAt).toISOString(),
      });
      setCode("");
      setDescription("");
      setUsageLimit("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Tạo mã thất bại");
    } finally {
      setSaving(false);
    }
  }

  async function toggleActive(p: PromotionOut) {
    try {
      await api.adminUpdatePromotion(p.id, { is_active: !p.is_active });
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Cập nhật thất bại");
    }
  }

  const columns: Column<PromotionOut>[] = [
    { key: "code", header: "Mã", cell: (p) => <span className="font-mono font-medium">{p.code}</span> },
    {
      key: "type",
      header: "Loại / Giá trị",
      cell: (p) => (
        <div>
          <p>{formatPromoType(p)}</p>
          {p.description && <p className="text-xs text-ink-muted">{p.description}</p>}
        </div>
      ),
    },
    {
      key: "usage",
      header: "Đã dùng / Giới hạn",
      align: "right",
      cell: (p) => `${p.used_count}${p.usage_limit != null ? `/${p.usage_limit}` : ""}`,
    },
    {
      key: "active",
      header: "Trạng thái",
      cell: (p) => <StatusBadge status={p.is_active ? "active" : "hidden"} />,
    },
    {
      key: "period",
      header: "Hiệu lực",
      cell: (p) => {
        const start = p.starts_at ? new Date(p.starts_at).toLocaleString("vi-VN") : "—";
        const end = p.expires_at ? new Date(p.expires_at).toLocaleString("vi-VN") : "—";
        return (
          <div className="text-xs">
            <p>{start}</p>
            <p className="text-ink-muted">→ {end}</p>
          </div>
        );
      },
    },
    {
      key: "actions",
      header: "",
      cell: (p) => (
        <button
          type="button"
          onClick={() => void toggleActive(p)}
          className="rounded-full border border-forest px-3 py-1 text-xs text-forest hover:bg-forest/8"
        >
          {p.is_active ? "Tắt" : "Bật"}
        </button>
      ),
    },
  ];

  return (
    <div>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl text-forest">Khuyến mãi</h1>
          <p className="mt-1 text-sm text-ink-muted">Tạo / bật tắt mã giảm giá.</p>
        </div>
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-4">
        <form onSubmit={onCreate} className="h-fit rounded-sm border border-line bg-surface p-4 lg:col-span-1">
          <h2 className="font-display text-xl text-forest">Thêm mã</h2>
          <div className="mt-4 grid gap-3">
            <Field label="Mã" value={code} onChange={setCode} required />
            <Field label="Mô tả" value={description} onChange={setDescription} />
            <label className="text-sm">
              <span className="text-ink-muted">Loại giảm</span>
              <select
                value={discountType}
                onChange={(e) => setDiscountType(e.target.value as DiscountType)}
                className="mt-1 block w-full rounded-sm border border-line bg-paper px-2 py-1.5"
              >
                <option value="percentage">Phần trăm</option>
                <option value="fixed_amount">Số tiền cố định</option>
                <option value="free_shipping">Miễn phí ship</option>
              </select>
            </label>
            <Field label="Giá trị (% hoặc đ)" value={discountValue} onChange={setDiscountValue} type="number" required />
            <Field label="ĐH tối thiểu (đ)" value={minSubtotal} onChange={setMinSubtotal} type="number" />
            <Field label="Giới hạn sử dụng" value={usageLimit} onChange={setUsageLimit} type="number" />
            <Field label="Bắt đầu" value={startsAt} onChange={setStartsAt} type="datetime-local" required />
            <Field label="Kết thúc" value={expiresAt} onChange={setExpiresAt} type="datetime-local" required />
          </div>
          {error && <p className="mt-3 text-sm text-danger">{error}</p>}
          <button
            type="submit"
            disabled={saving}
            className="mt-4 w-full rounded-full bg-forest px-4 py-2 text-sm font-medium text-white hover:bg-forest-deep disabled:opacity-50"
          >
            {saving ? "Đang lưu…" : "Tạo mã"}
          </button>
        </form>

        <div className="lg:col-span-3">
          <DataTable
            columns={columns}
            rows={promos}
            keyExtractor={(p) => p.id}
            loading={loading}
            empty="Chưa có khuyến mãi."
          />
        </div>
      </div>
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
        className="mt-1 block w-full rounded-sm border border-line bg-paper px-2 py-1.5 outline-none focus:border-moss"
      />
    </label>
  );
}
