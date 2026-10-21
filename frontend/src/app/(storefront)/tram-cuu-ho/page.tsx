import Link from "next/link";
import { api } from "@/lib/api-client";
import { PostCard } from "@/components/community/PostCard";

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
    const config = await api.communityConfig();
    if (!config.enabled) return <p className="p-8">Trạm cứu hộ đang tạm ngưng. Vui lòng quay lại sau.</p>;
    const [catalog, feed] = await Promise.all([api.communityLocations(), api.listCommunityPosts({
      post_type: (tab || undefined) as "lost_pet" | "found_pet" | "adoption" | undefined,
      province_id: params.province_id ? Number(params.province_id) : undefined,
      pet_type: (params.pet_type || undefined) as "dog" | "cat" | "other" | undefined,
      lifecycle_status: params.lifecycle_status || "open", cursor: params.cursor, limit: 12,
    })]);
    return <div className="space-y-6">
      <section className="rounded-2xl border border-forest/15 bg-forest/5 px-5 py-8 md:px-8 md:py-10">
        <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-moss">Cộng đồng Petshop · Trạm cứu hộ</p>
        <h1 className="font-display text-3xl text-forest md:text-4xl">{titles[tab] ?? "Cùng đưa các bé về nhà"}</h1>
        <p className="mt-3 max-w-xl leading-relaxed text-ink-muted">Kết nối những người đang tìm thú cưng, tìm chủ và sẵn sàng đón một thành viên mới.</p>
      </section>
      <form action="/tram-cuu-ho" className="flex flex-wrap items-end gap-3 rounded-sm border border-line bg-surface p-4">
        <input type="hidden" name="post_type" value={tab} />
        <label className="text-sm">Loài<select name="pet_type" defaultValue={params.pet_type ?? ""} className="mt-1 block rounded-sm border border-line p-2"><option value="">Tất cả</option><option value="dog">Chó</option><option value="cat">Mèo</option><option value="other">Khác</option></select></label>
        <label className="text-sm">Khu vực<select name="province_id" defaultValue={params.province_id ?? ""} className="mt-1 block max-w-full rounded-sm border border-line p-2"><option value="">Tất cả khu vực</option>{catalog.provinces.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}</select></label>
        <label className="text-sm">Trạng thái<select name="lifecycle_status" defaultValue={params.lifecycle_status ?? "open"} className="mt-1 block rounded-sm border border-line p-2"><option value="open">Đang mở</option><option value="resolved">Đã đoàn tụ / nhận nuôi</option><option value="closed">Đã đóng</option><option value="expired">Hết hạn</option></select></label>
        <button className="rounded-full bg-forest px-5 py-2 text-white">Lọc tin</button><Link href="/tram-cuu-ho" className="px-2 py-2 text-sm underline">Xóa bộ lọc</Link>
      </form>
      {feed.items.length ? <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">{feed.items.map(post => <PostCard key={post.id} post={post} />)}</div> : <div className="rounded-sm border border-line p-10 text-center"><p>Chưa có tin phù hợp.</p><Link href="/tram-cuu-ho/dang-tin" className="mt-3 inline-block text-forest underline">Đăng tin mới</Link></div>}
      <div className="flex justify-between">{params.cursor ? <Link href={link({ cursor: null })} className="text-forest underline">Về đầu danh sách</Link> : <span />}{feed.next_cursor && <Link href={link({ cursor: feed.next_cursor })} className="rounded-full border border-line px-5 py-2">Trang tiếp theo</Link>}</div>
    </div>;
  } catch {
    return <div className="space-y-3 p-8"><p role="alert">Không tải được tin hoặc bộ lọc không hợp lệ.</p><Link href="/tram-cuu-ho" className="text-forest underline">Tải lại danh sách</Link></div>;
  }
}
