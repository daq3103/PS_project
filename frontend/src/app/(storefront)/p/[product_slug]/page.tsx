import { pageMetadata, productDescription, productImage, productStructuredData } from "@/lib/seo";
import Image from "next/image";
import { notFound } from "next/navigation";
import { ProductCard } from "@/components/ProductCard";
import { VariantStockBox } from "@/components/VariantStockBox";
import { api, type ProductDto } from "@/lib/api-client";

const PET_LABEL: Record<string, string> = {
  dog: "Cho chó",
  cat: "Cho mèo",
  both: "Cho chó & mèo",
};

export async function generateMetadata({params}: {params: Promise<{product_slug: string}>}) {
  const {product_slug} = await params;
  try {
    const product = await api.getProductBySlug(product_slug);
    if (product.status !== "active") return {robots: {index: false}};
    return pageMetadata(product.seo_title || product.name, productDescription(product), `/p/${product.slug}`);
  } catch { return {title: "Không tìm thấy sản phẩm", robots: {index: false}}; }
}

export default async function ProductPage({ params }: { params: Promise<{ product_slug: string }> }) {
  const { product_slug } = await params;
  let product;
  try {
    product = await api.getProductBySlug(product_slug);
  } catch {
    notFound();
  }
  if (product.status !== "active") notFound();

  const initialStock = product.variants.map((v) => ({
    variant_id: v.id,
    title: v.title,
    unit: v.options?.unit || "cái",
    cached_available_qty: v.cached_available_qty,
    nearest_expiry_date: v.nearest_expiry_date,
    price: v.price,
    is_active: v.is_active,
  }));

  let related: ProductDto[] = [];
  try {
    related = await api.listProducts(
      `status=active&category_id=${product.category_id}&limit=4&sort=newest`,
    );
  } catch {
    related = [];
  }
  const relatedProducts = related.filter((p) => p.id !== product.id).slice(0, 4);

  const activeVariants = product.variants.filter((v) => v.is_active);
  const weights = activeVariants.map((v) => v.weight_grams ?? 0).filter((w) => w > 0);
  const minWeight = weights.length ? Math.min(...weights) : 0;
  const maxWeight = weights.length ? Math.max(...weights) : 0;

  const structuredData = productStructuredData(product);
  return (
    <article className="grid gap-10 md:grid-cols-2">
      {structuredData && <script type="application/ld+json" dangerouslySetInnerHTML={{__html: JSON.stringify(structuredData).replace(/</g, "\\u003c")}} />}
      <div className="group relative aspect-[4/5] overflow-hidden rounded-sm bg-forest/10 shadow-sm transition-shadow duration-200 hover:shadow-md">
        <Image
          src={productImage(product)}
          unoptimized
          alt={product.name}
          fill
          priority
          className="object-cover transition duration-500 group-hover:scale-105"
          sizes="(max-width: 768px) 100vw, 50vw"
        />
      </div>
      <div>
        <div className="flex flex-wrap items-center gap-2 text-sm text-ink-muted">
          {product.brand ? <span>{product.brand}</span> : null}
          {product.brand && product.pet_type ? (
            <span className="text-line">|</span>
          ) : null}
          {product.pet_type ? <span>{PET_LABEL[product.pet_type] ?? product.pet_type}</span> : null}
        </div>
        <h1 className="mt-2 font-display text-3xl leading-tight text-ink md:text-4xl">
          {product.name}
        </h1>
        {product.short_description && (
          <p className="mt-3 text-ink-muted">{product.short_description}</p>
        )}

        <VariantStockBox productId={product.id} initial={initialStock} />

        <div className="mt-8 space-y-4 border-t border-line pt-6 text-sm">
          <InfoRow label="Mã sản phẩm" value={product.slug} />
          {minWeight > 0 && (
            <InfoRow
              label="Khối lượng"
              value={minWeight === maxWeight ? `${minWeight} g` : `${minWeight}-${maxWeight} g`}
            />
          )}
          {activeVariants.length > 0 && (
            <InfoRow
              label="Kích cỡ"
              value={activeVariants
                .map((v) => [v.length_cm, v.width_cm, v.height_cm].filter(Boolean).join("×"))
                .filter(Boolean)
                .join(", ")}
            />
          )}
          {product.life_stage ? <InfoRow label="Giai đoạn" value={product.life_stage} /> : null}
        </div>

        {product.description && (
          <div className="mt-8 border-t border-line pt-6">
            <h2 className="font-display text-xl text-ink">Mô tả</h2>
            <div className="mt-3 whitespace-pre-line text-sm leading-relaxed text-ink-muted">
              {product.description}
            </div>
          </div>
        )}

        <div className="mt-8 grid gap-4 sm:grid-cols-2">
          <InfoCard title="Giao hàng">
            <ul className="list-disc space-y-1 pl-4 text-sm text-ink-muted">
              <li>Giao COD hoặc chuyển khoản VietQR</li>
              <li>Miễn phí vận chuyển tuỳ khu vực</li>
              <li>Đóng gói cẩn thận trước khi giao</li>
            </ul>
          </InfoCard>
          <InfoCard title="Đổi / trả">
            <ul className="list-disc space-y-1 pl-4 text-sm text-ink-muted">
              <li>Kiểm tra hàng trước khi thanh toán</li>
              <li>Liên hệ trong 24h nếu lỗi sản phẩm</li>
              <li>Giữ nguyên bao bì để đổi trả</li>
            </ul>
          </InfoCard>
        </div>
      </div>

      {relatedProducts.length > 0 && (
        <section className="mt-10 md:col-span-2">
          <h2 className="font-display text-2xl text-ink">Sản phẩm liên quan</h2>
          <div className="mt-5 grid gap-x-8 gap-y-10 sm:grid-cols-2 lg:grid-cols-4">
            {relatedProducts.map((p) => (
              <ProductCard key={p.id} product={p} />
            ))}
          </div>
        </section>
      )}
    </article>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-wrap gap-2">
      <span className="text-ink-muted">{label}:</span>
      <span className="font-medium text-ink">{value}</span>
    </div>
  );
}

function InfoCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-sm border border-line bg-surface p-4">
      <h3 className="font-medium text-ink">{title}</h3>
      <div className="mt-2">{children}</div>
    </div>
  );
}
