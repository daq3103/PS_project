import type { ReactNode } from "react";
import { SiteHeader } from "@/components/SiteHeader";
import { AnalyticsTracker } from "@/components/AnalyticsTracker";
import { ContactWidget } from "@/components/ContactWidget";
import { SiteFooter } from "@/components/SiteFooter";

export default function StorefrontLayout({ children }: { children: ReactNode }) {
  return (
    <>
      <AnalyticsTracker />
      <SiteHeader />
      <div className="mx-auto w-full max-w-6xl flex-1 px-4 py-8 md:px-6 md:py-10">
        {children}
      </div>
      <SiteFooter />
      <ContactWidget />
    </>
  );
}
