"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ProductCard } from "@/components/ProductCard";
import { api, type CartDto, type CategoryDto, type ProductDto } from "@/lib/api-client";
import { formatVnd } from "@/lib/format";

const PET_EMOJI: Record<string, string> = {
  dog: "🐕",
  cat: "🐈",
  both: "🐾",
};

function fallbackImage(slug: string | null): string {
  return slug?.includes("hat") || slug?.includes("food") || slug?.includes("pate")
    ? "/brand/cat-food.jpg" : "/brand/cat-accessories.jpg";
}

export default function CartPage() {
  const [cart, setCart] = useState<CartDto | null>(null);
  const [categories, setCategories] = useState<CategoryDto[]>([]);
  const [suggestions, setSuggestions] = useState<ProductDto[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);

  async function load() {
    setLoading(true);
    try {
      await api.me();
      let [cartData, cats, prods] = await Promise.all([
        api.getCart(),
        api.listCategories(true),
        api.listProducts("status=active&limit=4&sort=newest"),
      ]);
      // Keep an unfinished edit across an immediate refresh, scoped to this cart.
      try {
        const pending = JSON.parse(sessionStorage.getItem(`pethome:cart-drafts:${cartData.id}`) || "{}") as Record<string, string>;
        for (const item of cartData.items) {
          const value = pending[item.id];
          if (value && /^\d+$/.test(value) && Number(value) >= 1 && Number(value) <= 99 && Number(value) !== item.qty) {
            cartData = await api.updateCartItem(item.id, Number(value));
          }
        }
        sessionStorage.removeItem(`pethome:cart-drafts:${cartData.id}`);
      } catch (e) { setError(e instanceof Error ? e.message : "Chưa lưu được số lượng vừa nhập."); }
      setCart(cartData);
      setCategories(cats);
      setSuggestions(prods);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Không tải được giỏ");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  useEffect(() => {
    if (saving || !cart) return;
    const timer = window.setTimeout(() => {
      const entry = cart.items.find(item => drafts[item.id] !== undefined && /^\d+$/.test(drafts[item.id]) && Number(drafts[item.id]) >= 1 && Number(drafts[item.id]) <= 99 && Number(drafts[item.id]) !== item.qty);
      if (entry) void changeQty(entry.id, Number(drafts[entry.id]));
    }, 650);
    return () => window.clearTimeout(timer);
  // The timer uses the latest input and committed cart, and is reset on each edit.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [drafts, cart, saving]);

  async function changeQty(itemId: string, qty: number) {
    if (saving) return;
    setSaving(true);
    setError("");
    try {
      const data = await api.updateCartItem(itemId, qty);
      setCart(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Không cập nhật được số lượng");
    } finally {
      setDrafts(old => { const next = { ...old }; delete next[itemId]; if (cart) sessionStorage.setItem(`pethome:cart-drafts:${cart.id}`, JSON.stringify(next)); return next; });
      setSaving(false);
    }
  }

  function commitQty(itemId: string, previous: number) {
    const raw = drafts[itemId];
    if (raw === undefined) return;
    if (/^\d+$/.test(raw) && Number(raw) === previous) {
      setError("");
      return;
    }
    const qty = Number(raw);
    if (!/^\d+$/.test(raw) || !Number.isInteger(qty) || qty < 1 || qty > 99) {
      setError("Số lượng phải là số nguyên từ 1 đến 99. Chọn Xóa nếu muốn bỏ sản phẩm.");
      setDrafts(old => { const next = { ...old }; delete next[itemId]; if (cart) sessionStorage.setItem(`pethome:cart-drafts:${cart.id}`, JSON.stringify(next)); return next; });
      return;
    }
    void changeQty(itemId, qty);
  }

  async function remove(itemId: string) {
    setSaving(true);
    try {
      setCart(await api.removeCartItem(itemId));
      setError("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Không xóa được sản phẩm");
    } finally { setSaving(false); }
  }

  if (loading) return <p className="text-ink-muted">Đang tải giỏ hàng…</p>;
  if (error && !cart) return <p role="alert" className="text-danger">{error}</p>;
  if (!cart || cart.items.length === 0) {
    return (
      <div className="space-y-10">
        <div>
          <h1 className="font-display text-3xl text-ink">Giỏ hàng</h1>
          <p className="mt-3 text-ink/70">Chưa có sản phẩm trong giỏ.</p>
          <Link
            href="/shop"
            className="mt-5 inline-block rounded-full bg-forest px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition duration-200 hover:-translate-y-0.5 hover:bg-forest-deep hover:shadow-md"
          >
            Tiếp tục mua sắm
          </Link>
        </div>

        {categories.length > 0 && (
          <div>
            <h2 className="font-display text-xl text-ink">Duyệt theo danh mục</h2>
            <div className="mt-4 flex flex-wrap gap-2">
              {categories.map((c) => (
                <Link
                  key={c.id}
                  href={`/c/${c.slug}`}
                  className="rounded-full border border-line bg-surface px-4 py-2 text-sm text-ink transition duration-200 hover:-translate-y-0.5 hover:border-forest/40 hover:bg-moss/5"
                >
                  {c.name}
                </Link>
              ))}
            </div>
          </div>
        )}

        {suggestions.length > 0 && (
          <div>
            <h2 className="font-display text-xl text-ink">Gợi ý cho bạn</h2>
            <div className="mt-4 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
              {suggestions.map((p) => (
                <ProductCard key={p.id} product={p} />
              ))}
            </div>
          </div>
        )}
      </div>
    );
  }

  return (
    <div>
      <h1 className="font-display text-3xl text-ink">Giỏ hàng</h1>
      {error && <p role="alert" className="mt-3 text-danger">{error}</p>}
      <ul className="mt-8 divide-y divide-line border-y border-line">
        {cart.items.map((item) => (
          <li key={item.id} className="flex flex-wrap items-center justify-between gap-4 py-4">
            <div className="flex min-w-0 items-center gap-3">
              <Link href={`/p/${item.product_slug}`} className="shrink-0 overflow-hidden rounded-lg border border-line bg-forest/5 transition hover:border-forest/40">
                <img src={item.image_url || fallbackImage(item.product_slug)} onError={e => { e.currentTarget.onerror = null; e.currentTarget.src = fallbackImage(item.product_slug); }} alt={item.product_name || "Sản phẩm"} className="h-20 w-20 object-cover" />
              </Link>
              <div>
                <Link href={`/p/${item.product_slug}`} className="font-medium text-ink hover:text-forest">{item.product_name}</Link>
                <p className="text-sm text-ink/70">{item.title}</p>
                <p className="text-sm text-ink/70">{item.unit_price != null ? formatVnd(item.unit_price) : "—"}</p>
                {!item.is_available && <p className="mt-1 text-sm text-honey">{item.unavailable_label}</p>}
              </div>
            </div>
            <div className="flex items-center gap-3">
              <input
                type="number"
                min={1}
                max={99}
                aria-label={`Số lượng ${item.product_name}`}
                disabled={saving}
                value={drafts[item.id] ?? String(item.qty)}
                onChange={(e) => { const next = { ...drafts, [item.id]: e.target.value }; sessionStorage.setItem(`pethome:cart-drafts:${cart.id}`, JSON.stringify(next)); setDrafts(next); }}
                onBlur={() => commitQty(item.id, item.qty)}
                onKeyDown={e => { if (e.key === "Enter") e.currentTarget.blur(); }}
                className="w-16 rounded-sm border border-line bg-surface px-2 py-1 text-center transition duration-200 hover:border-forest/40 focus:border-forest focus:outline-none"
              />
              <button
                type="button"
                disabled={saving}
                onClick={() => void remove(item.id)}
                className="text-sm text-ink/70 hover:text-danger"
              >
                Xóa
              </button>
            </div>
          </li>
        ))}
      </ul>
      <div className="mt-6 flex flex-wrap items-center justify-between gap-4">
        <p className="text-lg">
          Tạm tính: <strong>{formatVnd(cart.subtotal)}</strong>
        </p>
        <Link
          href="/checkout"
          aria-disabled={saving}
          onClick={e => { if (saving) e.preventDefault(); }}
          className="rounded-full bg-forest px-5 py-2.5 text-sm font-medium text-white shadow-sm transition duration-200 hover:-translate-y-0.5 hover:bg-forest-deep hover:shadow-md"
        >
          Thanh toán
        </Link>
      </div>
    </div>
  );
}
