import Image from "next/image";
import Link from "next/link";
import { notFound } from "next/navigation";
import { api } from "@/lib/api-client";
import { ContactReveal } from "./ContactReveal";
import { AdoptionForm } from "@/components/community/AdoptionForm";
import { ReportForm } from "@/components/community/ReportForm";
import { lifeLabels } from "@/components/community/labels";

export const dynamic = "force-dynamic";

const TYPE_LABELS: Record<string, string> = {
  lost_pet: "Tin mất",
  found_pet: "Tin nhặt được",
  adoption: "Nhận nuôi",
};

const PET_LABELS: Record<string, string> = {
  dog: "Chó",
  cat: "Mèo",
  other: "Khác",
};

export default async function CommunityDetailPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  let post;
  try {
    post = await api.getCommunityPost(slug);
  } catch {
    notFound();
  }

  return (
    <div className="mx-auto w-full max-w-4xl px-4 py-8 md:px-6 md:py-10">
      <Link
        href="/tram-cuu-ho"
        className="text-sm text-forest hover:underline"
      >
        ← Quay lại Trạm cứu hộ
      </Link>

      <div className="mt-6 rounded-sm border border-line bg-surface p-5 md:p-8">
        <span className="rounded-full bg-forest px-3 py-1 text-xs font-medium text-white">
          {TYPE_LABELS[post.post_type]}
        </span>
        <h1 className="mt-4 font-display text-2xl text-ink md:text-3xl">
          {post.title}
        </h1>
        <p className="mt-2 font-medium text-forest">{post.lifecycle_status === "resolved" ? (post.post_type === "adoption" ? "Đã nhận nuôi" : "Đã đoàn tụ") : lifeLabels[post.lifecycle_status]}</p>
        {post.resolution_note && <p className="mt-2 text-sm">{post.resolution_note}</p>}
        <p className="mt-2 text-sm text-ink-muted">
          {PET_LABELS[post.pet_type]} {post.breed ? `· ${post.breed}` : ""}{" "}
          {post.color ? `· ${post.color}` : ""} · {post.province_name}
          {post.district_name ? `, ${post.district_name}` : ""}
        </p>

        {post.images.length > 0 && (
          <div className="mt-6 grid gap-3 sm:grid-cols-2">
            {post.images.map((img) => (
              <div key={img.upload_id} className="relative aspect-[4/3] overflow-hidden rounded-sm bg-forest/10">
                <Image
                  unoptimized
                  src={img.url}
                  alt={post.title}
                  fill
                  className="object-cover"
                  sizes="(max-width: 768px) 100vw, 50vw"
                />
              </div>
            ))}
          </div>
        )}

        <div className="mt-6 space-y-3 text-ink">
          <p className="whitespace-pre-wrap leading-relaxed">{post.description}</p>
        </div>

        <div className="mt-6 grid gap-4 border-t border-line pt-6 text-sm text-ink-muted sm:grid-cols-2">
          <div>
            <span className="block text-ink">Địa điểm</span>
            {post.location_detail}
            {post.ward_name ? `, ${post.ward_name}` : ""}
            {post.district_name ? `, ${post.district_name}` : ""}
            {`, ${post.province_name}`}
          </div>
          {post.event_at && (
            <div>
              <span className="block text-ink">
                {post.post_type === "lost_pet" ? "Lần thấy cuối" : "Thời điểm nhặt được"}
              </span>
              {new Date(post.event_at).toLocaleString("vi-VN")}
            </div>
          )}
        </div>

        {post.post_type === "adoption" && <div className="mt-6 space-y-2 rounded-sm bg-paper p-4 text-sm">
          <p>Tuổi ước tính: {post.adoption_meta.age_months == null ? "Chưa rõ" : `${post.adoption_meta.age_months} tháng`}</p>
          <p>Tiêm phòng: {post.adoption_meta.vaccinated == null ? "Chưa rõ" : post.adoption_meta.vaccinated ? "Đã tiêm" : "Chưa tiêm"}</p>
          <p>Triệt sản: {post.adoption_meta.neutered == null ? "Chưa rõ" : post.adoption_meta.neutered ? "Đã thực hiện" : "Chưa thực hiện"}</p>
          {post.adoption_meta.health && <p className="whitespace-pre-wrap">Sức khỏe: {post.adoption_meta.health}</p>}
          {post.adoption_meta.requirements && <p className="whitespace-pre-wrap">Điều kiện nhận nuôi: {post.adoption_meta.requirements}</p>}
        </div>}
        {post.lifecycle_status === "open" && new Date(post.expires_at).getTime() > Date.now() ? <div className="mt-6 space-y-6 border-t border-line pt-6">
          <ContactReveal slug={post.slug} />{post.post_type === "adoption" && <AdoptionForm postId={post.id} />}
        </div> : <p className="mt-6 text-sm text-ink-muted">Tin đã kết thúc tiếp nhận. Thông tin liên hệ được ẩn.</p>}
        <ReportForm postId={post.id} />
      </div>
    </div>
  );
}
