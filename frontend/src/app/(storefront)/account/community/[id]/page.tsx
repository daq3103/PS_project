"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { api, type CommunityPostOwnerOut } from "@/lib/api-client";
import { PostStatusBadge } from "@/components/community/PostStatusBadge";

export default function MyCommunityPostDetail() {
  const { id } = useParams<{ id: string }>();
  const [post, setPost] = useState<CommunityPostOwnerOut | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    void api.getMyCommunityPost(id).then(setPost).catch(e => setError(e instanceof Error ? e.message : "Không tải được tin"));
  }, [id]);
  return <div className="mx-auto max-w-3xl space-y-5">
    <Link href="/account/community" className="inline-block rounded-full px-3 py-2 text-forest hover:bg-forest/10">← Tin của tôi</Link>
    {error && <p role="alert" className="text-danger">{error}</p>}
    {!post && !error && <p>Đang tải tin…</p>}
    {post && <article className="space-y-5 rounded-2xl border border-line bg-surface p-5">
      <div className="flex flex-wrap items-start justify-between gap-3"><h1 className="font-display text-3xl">{post.title}</h1><PostStatusBadge moderationStatus={post.moderation_status} lifecycleStatus={post.lifecycle_status} /></div>
      {post.moderation_status !== "approved" && <p className="rounded-xl bg-forest/10 p-3 text-sm">Bản xem trước chỉ dành cho bạn. Tin sẽ hiển thị công khai sau khi được duyệt.</p>}
      {post.moderation_reason && <p className="text-sm text-danger">Lý do kiểm duyệt: {post.moderation_reason}</p>}
      <p className="whitespace-pre-wrap">{post.description}</p>
      <p className="text-sm text-ink-muted">{[post.location_detail, post.ward_name, post.district_name, post.province_name].filter(Boolean).join(", ")}</p>
      <div className="flex flex-wrap gap-3">{post.images.map(image => <img key={image.upload_id} src={image.url} alt={post.title} className="h-40 w-40 rounded-xl object-cover" />)}</div>
      {post.post_type !== "adoption" && <Link href={`/account/community/${post.id}/edit`} className="inline-block rounded-full border border-line px-4 py-2 text-sm text-forest">Sửa tin</Link>}
    </article>}
  </div>;
}
