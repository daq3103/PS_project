import Link from "next/link";
import { ProductCard } from "@/components/ProductCard";
import { api, type ProductDto } from "@/lib/api-client";

type Props = {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

export const revalidate = 60;

export default async function SearchPage({ searchParams }: Props) {
  const sp = await searchParams;
  const q = typeof sp.q === "string" ? sp.q.trim() : "";
  const petType = typeof sp.pet_type === "string" ? sp.pet_type : "";
  const sort = typeof sp.sort === "string" ? sp.sort : "newest";
  const minPrice = typeof sp.min_price === "string" ? sp.min_price : "";
  const maxPrice = typeof sp.max_price === "string" ? sp.max_price : "";

  const qs = new URLSearchParams({
    status: "active",
    sort,
    limit: "48",
  });
  if (q) qs.set("q", q);
  if (petType) qs.set("pet_type", petType);
  if (minPrice) qs.set("min_price", minPrice);
  if (maxPrice) qs.set("max_price", maxPrice);

  let products: ProductDto[] = [];
  try {
    products = await api.listProducts(qs.toString());
  } catch {
    products = [];
  }

  const filterHref = (next: Record<string, string>) => {
    const params = new URLSearchParams();
    const merged = {
      q,
      pet_type: petType,
      sort,
      min_price: minPrice,
      max_price: maxPrice,
      ...next,
    };
    if (merged.q) params.set("q", merged.q);
    if (merged.pet_type) params.set("pet_type", merged.pet_type);
    if (merged.sort && merged.sort !== "newest") params.set("sort", merged.sort);
    if (merged.min_price) params.set("min_price", merged.min_price);
    if (merged.max_price) params.set("max_price", merged.max_price);
    const s = params.toString();
    return s ? `/search?${s}` : "/search";
  };

  return (
    <div>
      <h1 className="font-display text-4xl text-ink">Tìm kiếm</h1>
      <form action="/search" method="get" className="mt-6 flex max-w-xl flex-wrap gap-2">
        <input
          name="q"
          defaultValue={q}
          placeholder="Tên sản phẩm, thương hiệu…"
          className="min-w-[12rem] flex-1 rounded-full border border-line bg-surface px-4 py-2.5 outline-none transition duration-200 hover:border-forest/40 focus:border-forest"
        />
        <input type="hidden" name="pet_type" value={petType} />
        <input type="hidden" name="sort" value={sort} />
        <button
          type="submit"
          className="rounded-full bg-forest px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition duration-200 hover:-translate-y-0.5 hover:bg-forest-deep hover:shadow-md"
        >
          Tìm
        </button>
      </form>

      <div className="mt-6 flex flex-wrap gap-2 border-b border-line pb-4 text-sm">
        <Chip href={filterHref({ pet_type: "" })} active={!petType} label="Tất cả" />
        <Chip href={filterHref({ pet_type: "dog" })} active={petType === "dog"} label="Chó" />
        <Chip href={filterHref({ pet_type: "cat" })} active={petType === "cat"} label="Mèo" />
        <span className="mx-1 text-line">|</span>
        <Chip href={filterHref({ sort: "newest" })} active={sort === "newest"} label="Mới nhất" />
        <Chip href={filterHref({ sort: "price_asc" })} active={sort === "price_asc"} label="Giá tăng" />
        <Chip href={filterHref({ sort: "price_desc" })} active={sort === "price_desc"} label="Giá giảm" />
        <span className="mx-1 text-line">|</span>
        <Chip
          href={filterHref({ min_price: "0", max_price: "200000" })}
          active={maxPrice === "200000"}
          label="< 200k"
        />
        <Chip
          href={filterHref({ min_price: "200000", max_price: "500000" })}
          active={minPrice === "200000" && maxPrice === "500000"}
          label="200–500k"
        />
        <Chip
          href={filterHref({ min_price: "500000", max_price: "" })}
          active={minPrice === "500000" && !maxPrice}
          label="> 500k"
        />
      </div>

      <p className="mt-4 text-sm text-ink-muted">
        {q ? `Kết quả cho “${q}”: ` : ""}
        {products.length} sản phẩm
      </p>

      {products.length === 0 ? (
        <p className="mt-8 text-ink-muted">Không tìm thấy sản phẩm phù hợp.</p>
      ) : (
        <div className="mt-8 grid gap-8 sm:grid-cols-2 lg:grid-cols-3">
          {products.map((p) => (
            <ProductCard key={p.id} product={p} />
          ))}
        </div>
      )}
    </div>
  );
}

function Chip({ href, active, label }: { href: string; active: boolean; label: string }) {
  return (
    <Link
      href={href}
      className={`rounded-full px-3 py-1.5 transition duration-200 ${
        active
          ? "bg-forest text-white"
          : "bg-surface text-ink-muted hover:-translate-y-0.5 hover:bg-moss/10 hover:text-forest"
      }`}
    >
      {label}
    </Link>
  );
}
