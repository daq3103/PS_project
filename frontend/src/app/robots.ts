import type { MetadataRoute } from "next";
import { indexingEnabled, siteOrigin } from "@/lib/seo";
export const dynamic = "force-dynamic";
export default function robots(): MetadataRoute.Robots {
  return {rules: {userAgent: "*", ...(indexingEnabled() ? {allow: "/"} : {disallow: "/"})},
    ...(siteOrigin() ? {sitemap: `${siteOrigin()}/sitemap.xml`} : {})};
}
