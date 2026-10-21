"use client";
import { useCallback, useEffect, useState } from "react";
import { api, type ReportOut, type CommunityPostAdminOut } from "@/lib/api-client";
import { CommunityAdminNav } from "@/components/community/AdminNav";

export default function Page() {
  const [rows, setRows] = useState<ReportOut[]>([]);
  const [post, setPost] = useState<CommunityPostAdminOut | null>(null);
  const [status, setStatus] = useState<"pending" | "resolved" | "dismissed">("pending");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [offset, setOffset] = useState(0);
  const load = useCallback(async () => { try { setRows(await api.adminListCommunityReports(status, offset)); setError(""); } catch (e) { setError(e instanceof Error ? e.message : "Không tải được báo cáo"); } }, [status, offset]);
  useEffect(() => { void load(); }, [load]);
  return <div className="space-y-4"><CommunityAdminNav /><h1 className="font-display text-2xl text-forest">Báo cáo vi phạm</h1>
    <label>Trạng thái<select value={status} onChange={e => { setStatus(e.target.value as typeof status); setOffset(0); }} className="ml-3 border border-line p-2"><option value="pending">Chưa xử lý</option><option value="resolved">Đã gỡ tin</option><option value="dismissed">Đã bác bỏ</option></select></label>
    {error && <p role="alert" className="text-danger">{error}</p>}
    {!rows.length && <p>Không có báo cáo phù hợp.</p>}
    {rows.map(row => <article key={row.id} className="space-y-3 rounded-sm border border-line bg-surface p-4">
      <p className="whitespace-pre-wrap">{row.reason}</p><button className="text-forest underline" onClick={async () => { try { setPost(await api.adminCommunityPost(row.post_id)); } catch (e) { setError(e instanceof Error ? e.message : "Không tải được tin"); } }}>Xem bài bị báo cáo</button>
      {row.status === "pending" && <form onSubmit={e => e.preventDefault()} className="space-y-3">
        <label className="block">Lý do xử lý<input name="reason" minLength={3} maxLength={500} required className="mt-1 w-full border border-line p-2" /></label>
        <div className="flex gap-3">{([ ["resolved", "Gỡ tin"], ["dismissed", "Bác bỏ báo cáo"] ] as const).map(([action, label]) => <button type="button" key={action} disabled={busy} className="rounded-full border border-line px-4 py-2" onClick={async e => {
          const form = e.currentTarget.form!; if (!form.reportValidity()) return;
          if (action === "resolved" && !window.confirm("Gỡ bài bị báo cáo và kết thúc hồ sơ nhận nuôi đang xử lý?")) return;
          setBusy(true); try { await api.adminHandleCommunityReport(row.id, action, String(new FormData(form).get("reason"))); await load(); } catch (e) { setError(e instanceof Error ? e.message : "Không xử lý được"); } finally { setBusy(false); }
        }}>{label}</button>)}</div>
      </form>}
    </article>)}
    <div className="flex gap-3"><button disabled={!offset || busy} onClick={() => setOffset(v => Math.max(0, v - 100))} className="rounded-full border px-4 py-2 disabled:opacity-40">Trang trước</button><button disabled={rows.length < 100 || busy} onClick={() => setOffset(v => v + 100)} className="rounded-full border px-4 py-2 disabled:opacity-40">Trang sau</button></div>
    {post && <section className="space-y-3 rounded-sm border border-forest p-5"><button onClick={() => setPost(null)} className="text-sm underline">Đóng chi tiết</button><h2 className="font-display text-xl">{post.title}</h2><p className="whitespace-pre-wrap">{post.description}</p><p>{post.moderation_status} · {post.lifecycle_status}</p><div className="flex flex-wrap gap-2">{post.images.map(image => <img key={image.upload_id} src={image.url} alt={post.title} className="h-40 w-40 object-cover" />)}</div></section>}
  </div>;
}
