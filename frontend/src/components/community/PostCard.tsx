"use client";

import Image from "next/image";
import Link from "next/link";
import type { CommunityPostPublicOut, PetOptions } from "@/lib/api-client";
import { lifeLabels } from "./labels";

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

export function PostCard({ post, options }: { post: CommunityPostPublicOut; options?: PetOptions }) {
  const thumb = post.images[0];
  return (
    <Link
      href={`/tram-cuu-ho/${post.slug}`}
      className="group block overflow-hidden rounded-sm border border-line bg-surface transition hover:border-forest/30 hover:shadow-sm"
    >
      <div className="relative aspect-[4/3] overflow-hidden bg-forest/10">
        {thumb ? (
          <Image
            unoptimized
            src={thumb.url}
            alt={post.title}
            fill
            className="object-cover transition duration-500 group-hover:scale-105"
            sizes="(max-width: 768px) 100vw, 33vw"
          />
        ) : (
          <div className="flex h-full items-center justify-center text-sm text-ink-muted">
            Chưa có ảnh
          </div>
        )}
        <span className="absolute left-2 top-2 rounded-full bg-forest px-2 py-1 text-xs font-medium text-white">
          {TYPE_LABELS[post.post_type]}
        </span>
      </div>
      <div className="p-4">
        <p className="mb-2 text-xs font-medium text-forest">{post.lifecycle_status === "resolved" ? (post.post_type === "adoption" ? "Đã nhận nuôi" : "Đã đoàn tụ") : post.lifecycle_status === "open" && post.post_type === "adoption" ? "Chờ nhận nuôi" : lifeLabels[post.lifecycle_status]}</p>
        <p className="text-xs text-ink-muted">
          {PET_LABELS[post.pet_type]} {post.breed ? `· ${post.breed}` : ""} {post.color ? `· ${post.color}` : ""}
        </p>
        {options && post.pet_details?.colors?.length > 0 && <p className="mt-1 text-xs text-ink-muted">{post.pet_details.colors.map(color => options.colors[color]).filter(Boolean).join(" · ")}{options.coat_lengths[post.pet_details.coat_length] ? ` · Lông ${options.coat_lengths[post.pet_details.coat_length].toLocaleLowerCase("vi-VN")}` : ""}</p>}
        <h3 className="mt-1 font-display text-lg leading-snug text-ink group-hover:text-forest">
          {post.title}
        </h3>
        <p className="mt-2 line-clamp-2 text-sm text-ink-muted">{post.description}</p>
        <div className="mt-3 flex items-center justify-between text-xs text-ink-muted">
          <span>{post.province_name}</span>
          {post.event_at ? (
            <span>{new Date(post.event_at).toLocaleDateString("vi-VN")}</span>
          ) : null}
        </div>
      </div>
    </Link>
  );
}
