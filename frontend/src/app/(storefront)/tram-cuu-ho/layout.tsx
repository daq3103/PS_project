import type { ReactNode } from "react";
import Link from "next/link";

export const metadata = { title: "Trạm cứu hộ", description: "Tìm thú cưng thất lạc, kết nối với chủ và nhận nuôi những bé đang cần mái ấm." };

export default function RescueLayout({ children }: { children: ReactNode }) {
  return <><nav aria-label="Khám phá trạm cứu hộ" className="mb-6 flex flex-wrap gap-2 text-sm">{[["/tram-cuu-ho/cac-be","Các bé tại trạm"],["/tram-cuu-ho","Tin cộng đồng"],["/tram-cuu-ho/bao-tin","Báo tin cần hỗ trợ"],["/tram-cuu-ho/dong-hanh","Đồng hành"],["/tram-cuu-ho/minh-bach","Minh bạch"]].map(([href,label]) => <Link key={href} href={href} className="rounded-full border border-line bg-surface px-4 py-2 text-forest hover:bg-moss/10">{label}</Link>)}</nav>{children}</>;
}
