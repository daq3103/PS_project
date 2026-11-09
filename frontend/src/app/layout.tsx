import { indexingEnabled, siteOrigin } from "@/lib/seo";
import { BRAND } from "@/lib/brand";
import type { Metadata } from "next";
import { Fraunces, Outfit } from "next/font/google";
import type { ReactNode } from "react";
import "./globals.css";

const outfit = Outfit({
  subsets: ["latin", "latin-ext"],
  variable: "--font-sans",
  display: "swap",
});

const fraunces = Fraunces({
  subsets: ["latin", "latin-ext"],
  variable: "--font-display",
  display: "swap",
});

export const dynamic = "force-dynamic";

export function generateMetadata(): Metadata { return {
  title: { default: `${BRAND.name} — Chăm sóc và kết nối thú cưng`, template: `%s | ${BRAND.name}` },
  applicationName: BRAND.name,
  description: BRAND.description,
  metadataBase: new URL(siteOrigin() || "http://localhost:3000"),
  robots: indexingEnabled() ? {index: true, follow: true} : {index: false, follow: false},
}; }

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="vi" className={`${outfit.variable} ${fraunces.variable}`}>
      <body className="flex min-h-screen flex-col font-sans antialiased">
        {children}
      </body>
    </html>
  );
}
