"use client";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api-client";
import { CommunityAdminNav } from "@/components/community/AdminNav";
export default function Page() {
  const [data, setData] = useState<Awaited<ReturnType<typeof api.adminCommunityMetrics>> | null>(null);
  const [error, setError] = useState("");
  const load = useCallback(async () => { try { setData(await api.adminCommunityMetrics()); setError(""); } catch (e) { setError(e instanceof Error ? e.message : "Không tải được"); } }, []);
  useEffect(() => { void load(); }, [load]);
  const labels: Record<string, string> = { pending_posts: "Tin chờ duyệt", pending_reports: "Báo cáo chưa xử lý", active_applications: "Hồ sơ đang xử lý", completed_adoptions: "Đã bàn giao", resolved_posts: "Tin có kết quả", pending_jobs: "Thông báo chờ xử lý", failed_jobs: "Công việc chưa xử lý thành công" };
  return <div className="space-y-4"><CommunityAdminNav /><h1 className="font-display text-2xl text-forest">Theo dõi vận hành cứu hộ</h1><button onClick={() => void load()} className="rounded-full border px-4 py-2">Làm mới</button>{error && <p role="alert">{error}</p>}
    {!data ? <p>Đang tải…</p> : <><dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">{Object.entries(labels).map(([key, label]) => <div key={key} className="rounded-sm border border-line p-5"><dt className="text-sm text-ink-muted">{label}</dt><dd className="mt-2 text-3xl text-forest">{String(data[key as keyof typeof data])}</dd></div>)}</dl><p>Tin chờ lâu nhất: {data.oldest_pending_at ? new Date(data.oldest_pending_at).toLocaleString("vi-VN", { timeZone: "Asia/Ho_Chi_Minh" }) : "Không có"}</p></>}
  </div>;
}
