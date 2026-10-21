import Link from "next/link";
import { notFound } from "next/navigation";
import { ProductCard } from "@/components/ProductCard";
import { api, type ProductDto } from "@/lib/api-client";

type Props = {
  params: Promise<{ category_slug: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

export const revalidate = 60;

export default async function CategoryPage({ params, searchParams }: Props) {
  const { category_slug } = await params;
  const sp = await searchParams;
  const petType = typeof sp.pet_type === "string" ? sp.pet_type : "";
  const sort = typeof sp.sort === "string" ? sp.sort : "newest";
  const minPrice = typeof sp.min_price === "string" ? sp.min_price : "";
  const maxPrice = typeof sp.max_price === "string" ? sp.max_price : "";
  const q = typeof sp.q === "string" ? sp.q.trim() : "";

  let category;
  try {
    category = await api.getCategoryBySlug(category_slug);
  } catch {
    notFound();
  }

  const qs = new URLSearchParams({
    status: "active",
    category_slug,
    sort,
    limit: "48",
  });
  if (petType) qs.set("pet_type", petType);
  if (minPrice) qs.set("min_price", minPrice);
  if (maxPrice) qs.set("max_price", maxPrice);
  if (q) qs.set("q", q);

  let products: ProductDto[] = [];
  try {
    products = await api.listProducts(qs.toString());
  } catch {
    products = [];
  }

  const filterHref = (next: Record<string, string>) => {
    const params = new URLSearchParams();
    const merged = {
      pet_type: petType,
      sort,
      min_price: minPrice,
      max_price: maxPrice,
      q,
      ...next,
    };
    if (merged.q) params.set("q", merged.q);
    if (merged.pet_type) params.set("pet_type", merged.pet_type);
    if (merged.sort && merged.sort !== "newest") params.set("sort", merged.sort);
    if (merged.min_price) params.set("min_price", merged.min_price);
    if (merged.max_price) params.set("max_price", merged.max_price);
    const s = params.toString();
    return s ? `/c/${category_slug}?${s}` : `/c/${category_slug}`;
  };

  return (
    <div>
      <h1 className="font-display text-4xl text-ink">{category.name}</h1>

      <form
        action={`/c/${category_slug}`}
        method="get"
        className="mt-6 flex max-w-md flex-wrap gap-2"
      >
        <input
          name="q"
          defaultValue={q}
          placeholder="Lọc trong danh mục…"
          className="min-w-[10rem] flex-1 rounded-full border border-line bg-surface px-4 py-2 text-sm outline-none transition duration-200 hover:border-forest/40 focus:border-forest"
        />
        {petType ? <input type="hidden" name="pet_type" value={petType} /> : null}
        {sort !== "newest" ? <input type="hidden" name="sort" value={sort} /> : null}
        <button
          type="submit"
          className="rounded-full border border-forest px-4 py-2 text-sm font-semibold text-forest shadow-sm transition duration-200 hover:-translate-y-0.5 hover:bg-forest/10 hover:shadow-md"
        >
          Lọc
        </button>
      </form>

      <div className="mt-4 flex flex-wrap gap-2 border-b border-line pb-4 text-sm">
        <FilterChip href={filterHref({ pet_type: "" })} active={!petType} label="Tất cả" />
        <FilterChip href={filterHref({ pet_type: "dog" })} active={petType === "dog"} label="Chó" />
        <FilterChip href={filterHref({ pet_type: "cat" })} active={petType === "cat"} label="Mèo" />
        <span className="mx-2 text-line">|</span>
        <FilterChip href={filterHref({ sort: "newest" })} active={sort === "newest"} label="Mới nhất" />
        <FilterChip
          href={filterHref({ sort: "price_asc" })}
          active={sort === "price_asc"}
          label="Giá tăng"
        />
        <FilterChip
          href={filterHref({ sort: "price_desc" })}
          active={sort === "price_desc"}
          label="Giá giảm"
        />
        <span className="mx-2 text-line">|</span>
        <FilterChip
          href={filterHref({ min_price: "", max_price: "200000" })}
          active={maxPrice === "200000" && !minPrice}
          label="< 200k"
        />
        <FilterChip
          href={filterHref({ min_price: "200000", max_price: "500000" })}
          active={minPrice === "200000" && maxPrice === "500000"}
          label="200–500k"
        />
        <FilterChip
          href={filterHref({ min_price: "500000", max_price: "" })}
          active={minPrice === "500000" && !maxPrice}
          label="> 500k"
        />
      </div>

      {products.length === 0 ? (
        <p className="mt-8 text-ink-muted">Chưa có sản phẩm trong danh mục này.</p>
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

function FilterChip({
  href,
  active,
  label,
}: {
  href: string;
  active: boolean;
  label: string;
}) {
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
