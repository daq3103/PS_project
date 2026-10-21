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

export default function CartPage() {
  const [cart, setCart] = useState<CartDto | null>(null);
  const [categories, setCategories] = useState<CategoryDto[]>([]);
  const [suggestions, setSuggestions] = useState<ProductDto[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    try {
      await api.me();
      const [cartData, cats, prods] = await Promise.all([
        api.getCart(),
        api.listCategories(true),
        api.listProducts("status=active&limit=4&sort=newest"),
      ]);
      setCart(cartData);
      setCategories(cats);
      setSuggestions(prods);
      setError("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Không tải được giỏ");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  async function changeQty(itemId: string, qty: number) {
    const data = await api.updateCartItem(itemId, qty);
    setCart(data);
  }

  async function remove(itemId: string) {
    const data = await api.removeCartItem(itemId);
    setCart(data);
  }

  if (loading) return <p className="text-ink-muted">Đang tải giỏ hàng…</p>;
  if (error) return <p className="text-danger">{error}</p>;
  if (!cart || cart.items.length === 0) {
    return (
      <div className="space-y-10">
        <div>
          <h1 className="font-display text-3xl text-ink">Giỏ hàng</h1>
          <p className="mt-3 text-ink/70">Chưa có sản phẩm trong giỏ.</p>
          <Link
            href="/"
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
      <ul className="mt-8 divide-y divide-line border-y border-line">
        {cart.items.map((item) => (
          <li key={item.id} className="flex flex-wrap items-center justify-between gap-4 py-4">
            <div>
              <Link
                href={`/p/${item.product_slug}`}
                className="font-medium text-ink hover:text-forest"
              >
                {item.product_name}
              </Link>
              <p className="text-sm text-ink/70">{item.title}</p>
              <p className="text-sm text-ink/70">
                {item.unit_price != null ? formatVnd(item.unit_price) : "—"}
              </p>
              {!item.is_available && (
                <p className="mt-1 text-sm text-honey">{item.unavailable_label}</p>
              )}
            </div>
            <div className="flex items-center gap-3">
              <input
                type="number"
                min={1}
                max={99}
                value={item.qty}
                onChange={(e) => void changeQty(item.id, Number(e.target.value) || 1)}
                className="w-16 rounded-sm border border-line bg-surface px-2 py-1 text-center transition duration-200 hover:border-forest/40 focus:border-forest focus:outline-none"
              />
              <button
                type="button"
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
          className="rounded-full bg-forest px-5 py-2.5 text-sm font-medium text-white shadow-sm transition duration-200 hover:-translate-y-0.5 hover:bg-forest-deep hover:shadow-md"
        >
          Thanh toán
        </Link>
      </div>
    </div>
  );
}
