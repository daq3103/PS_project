"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api, type CommunityPostOwnerOut } from "@/lib/api-client";
import { PostStatusBadge } from "@/components/community/PostStatusBadge";

const TYPE_LABELS: Record<string, string> = {
  lost_pet: "Tin mất",
  found_pet: "Tin nhặt được",
  adoption: "Nhận nuôi",
};

function notificationText(message: string): string {
  const legacy = message.match(/^Tin của bạn có kết quả kiểm duyệt: (approved|rejected|hidden)\.$/);
  if (!legacy) return message;
  return ({ approved: "Tin của bạn đã được duyệt.", rejected: "Tin của bạn bị từ chối.", hidden: "Tin của bạn đã được gỡ." })[legacy[1] as "approved" | "rejected" | "hidden"];
}

export default function MyCommunityPostsPage() {
  const [savedNotice, setSavedNotice] = useState("");
  const [posts, setPosts] = useState<CommunityPostOwnerOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notifications, setNotifications] = useState<Awaited<ReturnType<typeof api.communityNotifications>>>([]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setPosts(await api.listMyCommunityPosts());
      setNotifications(await api.communityNotifications());
      setError("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Không tải được");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
    const params = new URLSearchParams(window.location.search);
    if (params.has("created")) setSavedNotice("Đã gửi tin. Tin sẽ hiển thị sau khi được duyệt.");
    else if (params.has("updated")) setSavedNotice("Đã cập nhật tin. Tin sẽ được duyệt lại.");
  }, [load]);

  async function closePost(id: string) {
    try {
      if (!window.confirm("Đóng tin này?")) return;
      await api.transitionCommunityPost(id, { action: "close", version: posts.find(p => p.id === id)?.version });
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Thao tác thất bại");
    }
  }

  async function renewPost(id: string) {
    try {
      await api.transitionCommunityPost(id, { action: "renew", version: posts.find(p => p.id === id)?.version });
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Thao tác thất bại");
    }
  }

  if (loading) return <p className="text-ink-muted">Đang tải…</p>;
  if (error) return <div className="space-y-3"><p role="alert" className="text-danger">{error}</p><Link href="/login" className="text-forest underline">Đăng nhập</Link><button onClick={() => void load()} className="ml-4 underline">Thử lại</button></div>;

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h2 className="font-display text-xl text-ink">Tin của tôi</h2>
        <Link
          href="/tram-cuu-ho/dang-tin"
          className="rounded-full bg-forest px-4 py-2 text-sm font-medium text-white hover:bg-forest-deep"
        >
          Đăng tin mới
        </Link>
      </div>
      {savedNotice && <p role="status" className="mb-4 rounded-xl bg-forest/10 p-3 text-sm text-forest">{savedNotice}</p>}

      {error && <p className="mb-4 text-sm text-danger">{error}</p>}
      <Link href="/account/adoption-requests" className="mb-4 inline-block text-forest underline">Hồ sơ nhận nuôi của tôi</Link>
      <button onClick={() => void load()} className="mb-4 ml-4 text-sm text-forest underline">Làm mới danh sách</button>
      {!!notifications.length && <section className="mb-6 space-y-2 rounded-sm border border-line p-4"><h3 className="font-display text-lg">Thông báo cứu hộ</h3>{notifications.filter((item, index, all) => all.findIndex(other => other.message === item.message && other.href === item.href) === index).slice(0, 20).map(item => <div key={item.id} className="flex flex-wrap justify-between gap-2 text-sm"><Link href={item.href} className="text-forest">{notificationText(item.message)}</Link>{!item.read_at && <button className="underline" onClick={async () => { try { await api.readCommunityNotification(item.id); setNotifications(old => old.map(n => n.id === item.id ? { ...n, read_at: new Date().toISOString() } : n)); } catch (e) { setError(e instanceof Error ? e.message : "Không cập nhật được"); } }}>Đánh dấu đã đọc</button>}</div>)}</section>}

      {posts.length === 0 ? (
        <p className="text-ink-muted">Bạn chưa đăng tin nào.</p>
      ) : (
        <div className="space-y-3">
          {posts.map((post) => (
            <article
              key={post.id}
              className="rounded-sm border border-line bg-surface p-4"
            >
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <span className="text-xs text-forest">{TYPE_LABELS[post.post_type]}</span>
                  <h3 className="font-display text-lg text-ink">
                    <Link href={post.moderation_status === "approved" ? `/tram-cuu-ho/${post.slug}` : `/account/community/${post.id}`} className="hover:text-forest">
                      {post.title}
                    </Link>
                  </h3>
                </div>
                <PostStatusBadge
                  moderationStatus={post.moderation_status}
                  lifecycleStatus={post.lifecycle_status}
                />
              </div>
              <p className="mt-2 line-clamp-2 text-sm text-ink-muted">{post.description}</p>
              {post.moderation_reason && <p className="mt-2 text-sm text-danger">Lý do kiểm duyệt: {post.moderation_reason}</p>}
              <div className="mt-3 flex flex-wrap gap-2">
                {post.post_type !== "adoption" && <Link href={`/account/community/${post.id}/edit`} className="rounded-full border border-line px-3 py-1.5 text-xs">Sửa tin</Link>}
                {post.post_type !== "adoption" && post.lifecycle_status === "open" && <button className="rounded-full bg-forest px-3 py-1.5 text-xs text-white" onClick={async () => {
                  if (!window.confirm("Xác nhận pet đã đoàn tụ với chủ?")) return;
                  try { await api.transitionCommunityPost(post.id, { action: "resolve", version: post.version }); await load(); } catch (e) { setError(e instanceof Error ? e.message : "Không cập nhật được"); }
                }}>Đã đoàn tụ</button>}
                {post.post_type !== "adoption" && post.lifecycle_status === "open" && (
                  <button
                    type="button"
                    onClick={() => void closePost(post.id)}
                    className="rounded-full border border-line px-3 py-1.5 text-xs text-ink hover:bg-forest/8"
                  >
                    Đóng tin
                  </button>
                )}
                {post.post_type !== "adoption" && (post.lifecycle_status !== "open" || new Date(post.expires_at).getTime() - Date.now() <= 3 * 86400000) && (
                  <button
                    type="button"
                    onClick={() => void renewPost(post.id)}
                    className="rounded-full border border-line px-3 py-1.5 text-xs text-ink hover:bg-forest/8"
                  >
                    Làm mới
                  </button>
                )}
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
