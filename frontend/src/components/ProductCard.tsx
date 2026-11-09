import { productImage } from "@/lib/seo";
import Image from "next/image";
import Link from "next/link";
import type { ProductDto } from "@/lib/api-client";
import { formatVnd } from "@/lib/format";

function petLabel(petType: string): string {
  if (petType === "dog") return "Cho chó";
  if (petType === "cat") return "Cho mèo";
  return "Cho chó & mèo";
}

export function ProductCard({ product }: { product: ProductDto }) {
  const active = product.variants.filter((v) => v.is_active);
  const minPrice = active.length ? Math.min(...active.map((v) => v.price)) : null;
  const stock = active.reduce((s, v) => s + v.cached_available_qty, 0);

  return (
    <Link
      href={`/p/${product.slug}`}
      className="group block min-w-0 rounded-sm border border-transparent bg-surface p-3 transition duration-200 hover:border-line hover:shadow-sm"
    >
      <div className="relative mb-3 aspect-[4/3] overflow-hidden bg-forest/8">
        <Image
          src={productImage(product)}
          unoptimized
          alt={product.name}
          fill
          className="object-cover transition duration-500 group-hover:scale-105"
          sizes="(max-width: 768px) 100vw, 33vw"
        />
      </div>
      <p className="text-sm text-ink-muted transition group-hover:text-ink">
        {petLabel(product.pet_type)}
      </p>
      <h3 className="mt-1 font-display text-xl leading-snug text-ink transition group-hover:text-forest">
        {product.name}
      </h3>
      {product.brand && (
        <p className="mt-1 text-sm text-ink-muted transition group-hover:text-ink">
          {product.brand}
        </p>
      )}
      <div className="mt-2 flex flex-wrap items-baseline justify-between gap-3">
        <span className="font-semibold text-ink transition group-hover:text-forest">
          {minPrice != null ? `từ ${formatVnd(minPrice)}` : "—"}
        </span>
        <span className="text-sm text-ink-muted">
          {stock > 0 ? active.length > 1 ? `Tổng còn ${stock} (${active.length} loại)` : `Còn ${stock}` : "Hết hàng"}
        </span>
      </div>
    </Link>
  );
}
