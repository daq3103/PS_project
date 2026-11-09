"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api-client";

export function AddToCartButton({ variantId, availableQty, unit }: { variantId: string; availableQty: number; unit: string }) {
  const [state, setState] = useState<"idle" | "loading" | "done" | "error">("idle");
  const [msg, setMsg] = useState("");
  const [quantity, setQuantity] = useState("1");
  const maxQty = Math.min(99, Math.max(0, availableQty));
  const chosen = Number(quantity);
  const valid = /^\d+$/.test(quantity) && Number.isInteger(chosen) && chosen >= 1 && chosen <= maxQty;

  useEffect(() => { setQuantity("1"); setState("idle"); setMsg(""); }, [variantId]);

  async function onClick() {
    if (!valid) { setState("error"); setMsg(`Chọn từ 1 đến ${maxQty} ${unit || "cái"}.`); return; }
    setState("loading");
    try {
      const me = await api.me();
      if (!me.user) {
        window.location.assign(`/login?next=${encodeURIComponent(window.location.pathname + window.location.search)}`);
        return;
      }
      await api.addToCart(variantId, chosen);
      setState("done");
      setMsg(`Đã thêm ${chosen} ${unit || "cái"} vào giỏ`);
    } catch (e) {
      setState("error");
      setMsg(e instanceof Error ? e.message : "Lỗi");
    }
  }

  return (
    <div className="flex flex-col gap-2">
      <label className="text-sm text-ink-muted">Số lượng ({unit || "cái"})</label>
      <div className="flex items-center rounded-full border border-line bg-paper">
        <button type="button" aria-label="Giảm số lượng" disabled={state === "loading" || !valid || chosen <= 1} onClick={() => setQuantity(String(chosen - 1))} className="min-h-10 min-w-10 rounded-l-full text-lg text-forest hover:bg-forest/10 disabled:opacity-40">−</button>
        <input aria-label={`Số lượng ${unit || "cái"}`} type="number" min={1} max={maxQty} step={1} inputMode="numeric" value={quantity} onChange={e => { setQuantity(e.target.value); setMsg(""); }} className="w-16 bg-transparent text-center text-sm outline-none" />
        <button type="button" aria-label="Tăng số lượng" disabled={state === "loading" || !valid || chosen >= maxQty} onClick={() => setQuantity(String(chosen + 1))} className="min-h-10 min-w-10 rounded-r-full text-lg text-forest hover:bg-forest/10 disabled:opacity-40">+</button>
      </div>
      <button
        type="button"
        onClick={onClick}
        disabled={state === "loading" || !valid}
        className="rounded-full bg-forest px-5 py-2.5 text-sm font-medium text-white shadow-sm transition duration-200 hover:-translate-y-0.5 hover:bg-forest-deep hover:shadow-md disabled:opacity-60 disabled:hover:translate-y-0"
      >
        {state === "loading" ? "Đang thêm…" : "Thêm vào giỏ"}
      </button>
      {(msg || !valid) && (
        <p role={!valid || state === "error" ? "alert" : "status"} className={`text-xs ${!valid || state === "error" ? "text-danger" : "text-moss"}`}>{!valid ? maxQty > 0 ? `Chọn từ 1 đến ${maxQty} ${unit || "cái"}.` : "Sản phẩm hiện đã hết hàng." : msg}</p>
      )}
    </div>
  );
}
