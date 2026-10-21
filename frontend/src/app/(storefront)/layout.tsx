import Image from "next/image";
import type { ReactNode } from "react";
import { SiteHeader } from "@/components/SiteHeader";
import { AnalyticsTracker } from "@/components/AnalyticsTracker";

export default function StorefrontLayout({ children }: { children: ReactNode }) {
  return (
    <>
      <AnalyticsTracker />
      <SiteHeader />
      <div className="mx-auto w-full max-w-6xl flex-1 px-4 py-8 md:px-6 md:py-10">
        {children}
      </div>
      <footer className="mt-auto border-t border-line bg-surface/50">
        <div className="mx-auto max-w-6xl px-4 py-8 text-sm text-ink/80 md:px-6">
          <div className="flex items-center gap-3">
            <Image
              src="/brand/brand-mark.jpg"
              alt=""
              width={40}
              height={40}
              className="h-10 w-10 rounded-full object-cover"
            />
            <p className="font-display text-lg text-forest">Petshop</p>
          </div>
          <p className="mt-2">Chăm sóc thú cưng, kết nối những mái ấm.</p>
        </div>
      </footer>
    </>
  );
}
