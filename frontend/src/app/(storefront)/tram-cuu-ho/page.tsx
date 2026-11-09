import Link from "next/link";
import { api } from "@/lib/api-client";
import { PostCard } from "@/components/community/PostCard";
import { FeedFilters } from "@/components/community/FeedFilters";

export const dynamic = "force-dynamic";
const titles: Record<string, string> = { lost_pet: "Tìm thú cưng thất lạc", found_pet: "Tìm chủ cho bé", adoption: "Tìm một mái ấm" };

export default async function Page({ searchParams }: { searchParams: Promise<Record<string, string | undefined>> }) {
  const params = await searchParams;
  const tab = params.post_type ?? "";
  const link = (changes: Record<string, string | null>) => {
    const query = new URLSearchParams();
    for (const [key, value] of Object.entries(params)) if (value) query.set(key, value);
    for (const [key, value] of Object.entries(changes)) { if (value) query.set(key, value); else query.delete(key); }
    return `/tram-cuu-ho?${query}`;
  };
  try {
    const [config, catalog, options, feed] = await Promise.all([api.communityConfig(), api.communityLocations().catch(() => null), api.communityPetOptions().catch(() => null), api.listCommunityPosts({
      post_type: (tab || undefined) as "lost_pet" | "found_pet" | "adoption" | undefined,
      province_id: params.province_id ? Number(params.province_id) : undefined,
      pet_type: (params.pet_type || undefined) as "dog" | "cat" | "other" | undefined,
      lifecycle_status: params.lifecycle_status || "open", cursor: params.cursor, limit: 12,
      q: params.q, breed: params.breed, colors: params.colors,
      coat_length: params.coat_length, pattern: params.pattern, sex: params.sex, size: params.size,
      date_from: params.date_from, date_to: params.date_to,
    }).catch(() => null)]);
    if (!config.enabled) return <p className="p-8">Trạm cứu hộ đang tạm ngưng. Vui lòng quay lại sau.</p>;
    if (!catalog || !options) throw new Error("Không tải được bộ lọc cứu hộ");
    return <div className="space-y-6">
      <section className="rounded-2xl border border-forest/15 bg-forest/5 px-5 py-8 md:px-8 md:py-10">
        <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-moss">Cộng đồng yêu thú cưng · Trạm cứu hộ</p>
        <h1 className="font-display text-3xl text-forest md:text-4xl">{titles[tab] ?? "Cùng đưa các bé về nhà"}</h1>
        <p className="mt-3 max-w-xl leading-relaxed text-ink-muted">Kết nối những người đang tìm thú cưng, tìm chủ và sẵn sàng đón một thành viên mới.</p><div className="mt-5 flex flex-wrap gap-3"><Link href="/tram-cuu-ho/cac-be" className="rounded-full bg-forest px-5 py-2.5 text-sm font-semibold text-white">Theo dõi các bé tại trạm</Link><Link href="/tram-cuu-ho/bao-tin" className="rounded-full border border-forest px-5 py-2.5 text-sm text-forest">Báo tin cần hỗ trợ tại Hà Nội</Link></div>
      </section>
      <FeedFilters key={new URLSearchParams(Object.entries(params).filter((entry): entry is [string, string] => !!entry[1])).toString()} params={params} options={options} provinces={catalog.provinces} />
      {!feed ? <p role="alert" className="rounded-xl border border-line p-5 text-sm">Chưa tải được tin. Hãy kiểm tra lại bộ lọc, bảo đảm ngày bắt đầu không sau ngày kết thúc, rồi thử lại.</p> : feed.items.length ? <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">{feed.items.map(post => <PostCard key={post.id} post={post} options={options} />)}</div> : <div className="space-y-3 rounded-sm border border-line p-10 text-center"><p>Chưa có tin phù hợp.</p><p className="text-sm text-ink-muted">Thử bỏ bớt màu lông, giống hoặc mở rộng khoảng ngày và khu vực.</p><Link href={tab ? `/tram-cuu-ho?post_type=${encodeURIComponent(tab)}` : "/tram-cuu-ho"} className="inline-block text-forest underline">Xem tất cả tin trong mục này</Link><br /><Link href="/tram-cuu-ho/dang-tin" className="inline-block text-sm text-forest underline">Đăng tin mới</Link></div>}
      <div className="flex justify-between">{params.cursor ? <Link href={link({ cursor: null })} className="text-forest underline">Về đầu danh sách</Link> : <span />}{feed?.next_cursor && <Link href={link({ cursor: feed.next_cursor })} className="rounded-full border border-line px-5 py-2">Trang tiếp theo</Link>}</div>
    </div>;
  } catch {
    return <div className="space-y-3 p-8"><p role="alert">Không tải được tin hoặc bộ lọc không hợp lệ.</p><Link href="/tram-cuu-ho" className="text-forest underline">Tải lại danh sách</Link></div>;
  }
}
