"use client";

import { useState } from "react";
import { api } from "@/lib/api-client";

export function AddToCartButton({ variantId }: { variantId: string }) {
  const [state, setState] = useState<"idle" | "loading" | "done" | "error">("idle");
  const [msg, setMsg] = useState("");

  async function onClick() {
    setState("loading");
    try {
      await api.me();
      await api.addToCart(variantId, 1);
      setState("done");
      setMsg("Đã thêm vào giỏ");
    } catch (e) {
      setState("error");
      setMsg(e instanceof Error ? e.message : "Lỗi");
    }
  }

  return (
    <div className="flex flex-col gap-2">
      <button
        type="button"
        onClick={onClick}
        disabled={state === "loading"}
        className="rounded-full bg-forest px-5 py-2.5 text-sm font-medium text-white shadow-sm transition duration-200 hover:-translate-y-0.5 hover:bg-forest-deep hover:shadow-md disabled:opacity-60 disabled:hover:translate-y-0"
      >
        {state === "loading" ? "Đang thêm…" : "Thêm vào giỏ"}
      </button>
      {msg && (
        <p className={`text-xs ${state === "error" ? "text-danger" : "text-moss"}`}>{msg}</p>
      )}
    </div>
  );
}
