import type { MetadataRoute } from "next";
import { api } from "@/lib/api-client";
import { siteOrigin } from "@/lib/seo";
export const dynamic = "force-dynamic";
export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const origin = siteOrigin();
  if (!origin) return [];
  const categories = await api.listCategories();
  const entries: MetadataRoute.Sitemap = ["/", "/shop", ...categories.map(c => `/c/${c.slug}`)].map(path => ({url: origin + path}));
  for (let offset = 0; ; offset += 200) {
    const products = await api.listProducts(`limit=200&offset=${offset}&status=active`);
    entries.push(...products.filter(p => p.status === "active").map(p => ({url: `${origin}/p/${p.slug}`})));
    if (products.length < 200) break;
  }
  return entries;
}
