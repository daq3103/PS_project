"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api-client";
import { formatVnd } from "@/lib/format";
import { AddToCartButton } from "./AddToCartButton";

type StockRow = {
  variant_id: string;
  title: string;
  cached_available_qty: number;
  nearest_expiry_date: string | null;
  price: number;
  is_active: boolean;
};

export function VariantStockBox({
  productId,
  initial,
}: {
  productId: string;
  initial: StockRow[];
}) {
  const [rows, setRows] = useState(initial);
  const [selected, setSelected] = useState(initial.find((r) => r.is_active)?.variant_id ?? "");

  useEffect(() => {
    let alive = true;
    const tick = async () => {
      try {
        const data = await api.getStock(productId);
        if (!alive) return;
        setRows(
          data.variants.map((v) => ({
            variant_id: v.variant_id,
            title: v.title,
            cached_available_qty: v.cached_available_qty,
            nearest_expiry_date: v.nearest_expiry_date,
            price: v.price,
            is_active: v.is_active,
          })),
        );
      } catch {
        /* keep initial */
      }
    };
    const id = setInterval(tick, 25000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, [productId]);

  const current = rows.find((r) => r.variant_id === selected) ?? rows[0];

  return (
    <div className="mt-6 space-y-4 rounded-sm border border-line bg-surface p-4 md:p-5">
      <p className="text-sm font-medium text-ink">Chọn loại</p>
      <div className="flex flex-wrap gap-2">
        {rows
          .filter((r) => r.is_active)
          .map((r) => (
            <button
              key={r.variant_id}
              type="button"
              onClick={() => setSelected(r.variant_id)}
              className={`rounded-full border px-4 py-2 text-sm transition duration-200 ${
                selected === r.variant_id
                  ? "border-forest bg-forest text-white"
                  : "border-line bg-paper text-ink hover:-translate-y-0.5 hover:border-forest/40 hover:bg-moss/5"
              }`}
              aria-pressed={selected === r.variant_id}
            >
              {r.title}
            </button>
          ))}
      </div>
      {current && (
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="font-display text-2xl text-ink">{formatVnd(current.price)}</p>
            <p className="mt-1 text-sm text-ink-muted">
              Còn {current.cached_available_qty}
            </p>
            {current.nearest_expiry_date ? (
              <p className="mt-0.5 text-sm text-ink-muted">
                HSD gần nhất {current.nearest_expiry_date}
              </p>
            ) : null}
          </div>
          {current.cached_available_qty > 0 ? (
            <AddToCartButton variantId={current.variant_id} />
          ) : (
            <span className="text-sm text-danger">Hết hàng</span>
          )}
        </div>
      )}
      <p className="text-[11px] text-ink-muted">Tồn kho làm mới ≤ 30 giây</p>
    </div>
  );
}
