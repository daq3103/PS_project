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
  const brand = typeof sp.brand === "string" ? sp.brand : "";
  const lifeStage = typeof sp.life_stage === "string" ? sp.life_stage : "";
  const inStock = sp.in_stock === "true";
  const requestedPage = Number(sp.page);
  const page = Number.isInteger(requestedPage) && requestedPage > 0 && requestedPage <= 10000 ? requestedPage : 1;
  let failed = false;

  const qs = new URLSearchParams({
    status: "active",
    sort,
    limit: "25",
    offset: String((page - 1) * 24),
  });
  if (q) qs.set("q", q);
  if (petType) qs.set("pet_type", petType);
  if (minPrice) qs.set("min_price", minPrice);
  if (maxPrice) qs.set("max_price", maxPrice);

  if (brand) qs.set("brand", brand);
  if (lifeStage) qs.set("life_stage", lifeStage);
  if (inStock) qs.set("in_stock", "true");
  let products: ProductDto[] = [];
  try {
    products = await api.listProducts(qs.toString());
  } catch {
    failed = true;
  }
  const hasNext = products.length > 24;
  products = products.slice(0, 24);

  const filterHref = (next: Record<string, string>) => {
    const params = new URLSearchParams();
    const merged = {
      q,
      brand,
      life_stage: lifeStage,
      in_stock: inStock ? "true" : "",
      page: "",
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
    if (merged.brand) params.set("brand", merged.brand);
    if (merged.life_stage) params.set("life_stage", merged.life_stage);
    if (merged.in_stock) params.set("in_stock", merged.in_stock);
    if (merged.page) params.set("page", merged.page);
    const s = params.toString();
    return s ? `/search?${s}` : "/search";
  };

  return (
    <div>
      <h1 className="font-display text-4xl text-ink">Tìm kiếm</h1>
      <form action="/search" method="get" className="mt-6 grid items-end gap-4 sm:grid-cols-2 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)_minmax(0,1fr)_auto_auto]">
        <input
          aria-label="Từ khóa tìm kiếm"
          name="q"
          defaultValue={q}
          placeholder="Tên sản phẩm, thương hiệu, mã hàng…"
          className="w-full min-w-0 rounded-full border border-line bg-surface px-4 py-2.5 outline-none transition duration-200 hover:border-forest/40 focus:border-forest"
        />
        <input type="hidden" name="pet_type" value={petType} />
        <input type="hidden" name="sort" value={sort} />
        <input type="hidden" name="min_price" value={minPrice} />
        <input type="hidden" name="max_price" value={maxPrice} />
        <label className="text-sm">Thương hiệu<input name="brand" defaultValue={brand} maxLength={100} className="mt-1 block w-full rounded-xl border border-line bg-surface px-3 py-2" /></label>
        <label className="text-sm">Độ tuổi<select name="life_stage" defaultValue={lifeStage} className="mt-1 block w-full rounded-xl border border-line bg-surface px-3 py-2"><option value="">Tất cả độ tuổi</option><option value="baby">Thú cưng nhỏ tuổi</option><option value="adult">Trưởng thành</option><option value="senior">Lớn tuổi</option></select></label>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" name="in_stock" value="true" defaultChecked={inStock} />Chỉ hiện còn hàng</label>
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
        Trang {page} · {products.length} sản phẩm
      </p>

      {failed ? <p role="alert" className="mt-6 text-danger">Chưa tải được danh sách sản phẩm. Vui lòng thử lại sau.</p> : products.length === 0 ? (
        <p className="mt-8 text-ink-muted">Không tìm thấy sản phẩm phù hợp. <Link href="/search" className="text-forest underline">Bỏ bộ lọc</Link></p>
      ) : (
        <div className="mt-8 grid gap-8 sm:grid-cols-2 lg:grid-cols-3">
          {products.map((p) => (
            <ProductCard key={p.id} product={p} />
          ))}
        </div>
      )}
      {!failed && <nav aria-label="Phân trang sản phẩm" className="mt-8 flex justify-between text-sm text-forest">{page > 1 ? <Link href={filterHref({page: String(page - 1)})}>← Trang trước</Link> : <span />}{hasNext && <Link href={filterHref({page: String(page + 1)})}>Trang sau →</Link>}</nav>}
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
