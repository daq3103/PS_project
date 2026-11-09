import type { Metadata } from "next";
import type { ProductDto } from "./api-client";

export function siteOrigin(): string | null {
  try {
    const url = new URL(process.env.SITE_URL || "");
    if (url.protocol !== "https:" || url.hostname.endsWith(".trycloudflare.com") || url.hostname === "localhost") return null;
    return url.origin;
  } catch { return null; }
}
export function indexingEnabled(): boolean {
  return !!siteOrigin() && process.env.SEO_ALLOW_INDEXING === "true";
}
export function pageMetadata(title: string, description: string, path: string): Metadata {
  const origin = siteOrigin();
  return { title, description, ...(origin ? {alternates: {canonical: origin + path}, openGraph: {title, description, url: origin + path, locale: "vi_VN", type: "website"}} : {}) };
}
export function productImage(product: ProductDto): string {
  return [...(product.images || [])].sort((a,b) => a.sort_order - b.sort_order)[0]?.r2_url || "/brand/cat-accessories.jpg";
}
export function productDescription(product: ProductDto): string {
  return product.seo_description?.trim() || product.short_description?.trim() || product.description?.trim().slice(0, 180) || `${product.name}${product.brand ? ` của ${product.brand}` : ""}. Xem giá, lựa chọn sản phẩm và tình trạng hàng tại PetHome.`;
}
export function productStructuredData(product: ProductDto) {
  const origin = siteOrigin();
  if (!origin) return null;
  const variants = product.variants.filter(v => v.is_active);
  const image = product.images?.length ? new URL(productImage(product), origin).href : undefined;
  return {"@context": "https://schema.org", "@type": "Product", name: product.name,
    description: productDescription(product), url: `${origin}/p/${product.slug}`,
    ...(image ? {image: [image]} : {}), ...(product.brand ? {brand: {"@type": "Brand", name: product.brand}} : {}),
    offers: variants.map(v => ({"@type": "Offer", name: v.title, sku: v.sku, price: v.price, priceCurrency: "VND",
      url: `${origin}/p/${product.slug}`, availability: `https://schema.org/${v.cached_available_qty > 0 ? "InStock" : "OutOfStock"}`}))};
}
