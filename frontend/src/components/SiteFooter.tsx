import Image from "next/image";
import Link from "next/link";
import { SOCIAL_CHANNELS, SOCIAL_LINKS } from "@/config/social-links";
import { BRAND } from "@/lib/brand";
import { SocialIcon } from "./SocialIcon";

export function SiteFooter() {
  return <footer className="mt-auto border-t border-line bg-surface/80">
    <div className="mx-auto grid max-w-6xl gap-8 px-4 py-10 md:grid-cols-[1.3fr_.7fr_1fr] md:gap-10 md:px-6 md:py-12">
      <div><Link href="/" className="inline-flex items-center gap-3"><Image src="/brand/brand-mark.jpg" alt="" width={44} height={44} className="h-11 w-11 rounded-full object-cover" /><span className="font-display text-2xl text-forest">{BRAND.name}</span></Link><p className="mt-4 max-w-xs text-sm leading-7 text-ink-muted">{BRAND.tagline}</p><p className="mt-2 max-w-xs text-sm leading-7 text-ink-muted">Một nơi để sẻ chia, chăm sóc và tìm mái ấm cho những người bạn nhỏ.</p></div>
      <nav aria-label="Khám phá PetHome"><h2 className="text-sm font-semibold text-forest">Khám phá</h2><ul className="mt-4 space-y-3 text-sm text-ink-muted"><li><Link href="/" className="hover:text-forest hover:underline">Trang chủ</Link></li><li><Link href="/tram-cuu-ho" className="hover:text-forest hover:underline">Trạm cứu hộ</Link></li><li><Link href="/shop" className="hover:text-forest hover:underline">Shop thú cưng</Link></li><li><Link href="/account/support" className="hover:text-forest hover:underline">Hỗ trợ khách hàng</Link></li></ul></nav>
      <nav aria-label="Mạng xã hội PetHome"><h2 className="text-sm font-semibold text-forest">Kết nối cùng {BRAND.name}</h2><p className="mt-3 text-sm leading-relaxed text-ink-muted">Theo dõi những câu chuyện và chia sẻ cùng cộng đồng.</p><ul className="mt-4 flex flex-wrap gap-2">{SOCIAL_CHANNELS.map(channel => <li key={channel.id}><a href={SOCIAL_LINKS[channel.id]} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-2 rounded-full border border-line bg-surface py-1 pl-1 pr-3 text-xs font-semibold text-ink transition hover:border-moss/50 hover:bg-paper"><SocialIcon channel={channel.id} compact />{channel.label}<span className="sr-only"> (mở trong tab mới)</span></a></li>)}</ul></nav>
    </div>
    <div className="border-t border-line/70"><div className="mx-auto flex max-w-6xl flex-col gap-2 px-4 pb-24 pt-5 text-xs text-ink-muted sm:flex-row sm:justify-between md:px-6 md:pb-6 md:pr-44"><p>© {new Date().getFullYear()} {BRAND.name}.</p><p>Yêu thương thú cưng, kết nối cộng đồng.</p></div></div>
  </footer>;
}
