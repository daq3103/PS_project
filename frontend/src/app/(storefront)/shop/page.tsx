import { pageMetadata } from "@/lib/seo";
import Image from "next/image";
import Link from "next/link";
import { ProductCard } from "@/components/ProductCard";
import { api, type CategoryDto, type ProductDto } from "@/lib/api-client";

export function generateMetadata() { return pageMetadata("Shop thú cưng — Thức ăn và đồ dùng chó mèo", "Khám phá thức ăn, đồ dùng và phụ kiện dành cho chó mèo tại PetHome. Xem giá, lựa chọn sản phẩm và tình trạng hàng.", "/shop"); }

export const revalidate = 60;

const CATEGORY_ART: Record<string, string> = {
  "thuc-an-hat": "/brand/cat-food.jpg",
  "phu-kien": "/brand/cat-accessories.jpg",
};

export default async function ShopPage() {
  let products: ProductDto[] = [];
  let categories: CategoryDto[] = [];
  try {
    [products, categories] = await Promise.all([
      api.listProducts("status=active&limit=12&sort=newest"),
      api.listCategories(true),
    ]);
  } catch {
    products = [];
    categories = [];
  }

  const cats =
    categories.length > 0
      ? categories
      : ([
          {
            id: "1",
            name: "Thức ăn hạt",
            slug: "thuc-an-hat",
            sort_order: 1,
            is_active: true,
          },
          {
            id: "2",
            name: "Phụ kiện",
            slug: "phu-kien",
            sort_order: 2,
            is_active: true,
          },
        ] as CategoryDto[]);

  return (
    <div>
      {/* Full-bleed hero — brand as hero signal + one photo. Single load motion on image. */}
      <section className="relative -mx-4 mb-12 overflow-hidden md:-mx-6">
        <div className="absolute inset-0">
          <Image
            src="/brand/hero-pets.jpg"
            alt=""
            fill
            priority
            className="animate-hero-image object-cover object-center"
            sizes="100vw"
          />
          <div className="absolute inset-0 bg-gradient-to-r from-forest-deep/75 via-forest/55 to-forest/20" />
        </div>

        <div className="relative mx-auto flex min-h-[60vh] max-w-6xl flex-col justify-end px-4 pb-12 pt-24 md:min-h-[65vh] md:px-6 md:pb-16 md:pt-32">
          <h1 className="max-w-2xl font-display text-3xl leading-[1.1] text-white md:text-5xl">
            Đồ dùng chó mèo chọn lọc, giao tận nhà
          </h1>
          <p className="mt-4 max-w-md text-base leading-relaxed text-white/90 md:text-lg">
            Thức ăn, pate, vòng cổ và phụ kiện — giá trực tiếp, tồn kho rõ ràng.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link
              href="/c/thuc-an-hat"
              className="rounded-full bg-white px-6 py-3 text-sm font-semibold text-forest shadow-sm transition duration-200 hover:-translate-y-0.5 hover:bg-paper hover:shadow-md"
            >
              Xem thức ăn
            </Link>
            <Link
              href="/c/phu-kien"
              className="rounded-full border border-white/55 px-6 py-3 text-sm font-semibold text-white shadow-sm transition duration-200 hover:-translate-y-0.5 hover:bg-white/15"
            >
              Xem phụ kiện
            </Link>
          </div>
        </div>
      </section>

      <section className="mb-16">
        <h2 className="font-display text-3xl text-ink">Danh mục</h2>
        <p className="mt-2 max-w-prose text-ink-muted">
          Chọn theo loại đồ bạn cần cho thú cưng.
        </p>
        <div className="mt-6 grid gap-4 sm:grid-cols-2">
          {cats.map((c) => (
            <Link
              key={c.id}
              href={`/c/${c.slug}`}
              className="group relative block aspect-[16/9] overflow-hidden rounded-sm"
            >
              <Image
                src={CATEGORY_ART[c.slug] ?? "/brand/bg-texture.jpg"}
                alt=""
                fill
                className="object-cover transition duration-500 group-hover:scale-105"
                sizes="(max-width: 768px) 100vw, 50vw"
              />
              <div className="absolute inset-0 bg-gradient-to-t from-forest-deep/75 via-transparent to-transparent transition duration-300 group-hover:from-forest-deep/85" />
              <div className="absolute bottom-0 left-0 p-5">
                <span className="font-display text-2xl text-white">{c.name}</span>
              </div>
            </Link>
          ))}
        </div>
      </section>

      <section>
        <div className="mb-6 flex items-end justify-between gap-4">
          <h2 className="font-display text-3xl text-ink">Sản phẩm mới</h2>
          <Link
            href="/c/thuc-an-hat"
            className="text-sm font-semibold text-forest underline-offset-4 transition duration-200 hover:text-forest-deep hover:underline"
          >
            Xem tất cả
          </Link>
        </div>
        {products.length === 0 ? (
          <div className="border-y border-line py-10">
            <p className="font-display text-xl text-ink">Chưa có sản phẩm để xem</p>
            <p className="mt-2 text-ink-muted">Quay lại sau hoặc xem danh mục khi shop cập nhật hàng.</p>
            <Link
              href="/c/thuc-an-hat"
              className="mt-5 inline-block rounded-full bg-forest px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition duration-200 hover:-translate-y-0.5 hover:bg-forest-deep hover:shadow-md"
            >
              Xem danh mục
            </Link>
          </div>
        ) : (
          <div className="grid gap-x-8 gap-y-10 sm:grid-cols-2 lg:grid-cols-3">
            {products.map((p) => (
              <ProductCard key={p.id} product={p} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
