"use client";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api, type AdoptionRequestOut } from "@/lib/api-client";
import { adoptionLabels } from "@/components/community/labels";

export default function Page() {
  const [rows, setRows] = useState<AdoptionRequestOut[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState("");
  const load = useCallback(async () => {
    try { setRows(await api.myAdoptionRequests()); setError(""); }
    catch (e) { setError(e instanceof Error ? e.message : "Không tải được hồ sơ"); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { void load(); }, [load]);
  return <div className="mx-auto max-w-3xl space-y-4 px-4 py-8"><h1 className="font-display text-3xl text-forest">Hồ sơ nhận nuôi của tôi</h1>
    {error && <p role="alert" className="text-danger">{error} <Link href="/login">Đăng nhập</Link></p>}
    {loading ? <p>Đang tải…</p> : !rows.length && <p>Bạn chưa gửi hồ sơ nào. <Link href="/tram-cuu-ho?post_type=adoption" className="underline">Tìm bé nhận nuôi</Link></p>}
    {rows.map(row => <article key={row.id} className="space-y-3 rounded-sm border border-line bg-surface p-5">
      <Link href={`/tram-cuu-ho/${row.post_slug}`} className="font-display text-xl text-forest">{row.post_title}</Link>
      <p>{adoptionLabels[row.status]}</p>{row.outcome_reason && <p>{row.outcome_reason}</p>}
      <p className="text-sm text-ink-muted">Cập nhật: {new Date(row.updated_at).toLocaleString("vi-VN", { timeZone: "Asia/Ho_Chi_Minh" })}</p>
      {row.anonymized_at ? <p>Thông tin cá nhân đã được xóa theo thời hạn lưu hồ sơ.</p> : <p className="text-sm">{row.applicant_name} · {row.applicant_phone}</p>}
      {["pending", "contacted", "approved"].includes(row.status) && <button disabled={busy === row.id} onClick={async () => {
        if (!window.confirm("Rút hồ sơ nhận nuôi này?")) return;
        setBusy(row.id); try { await api.withdrawAdoption(row.id); await load(); } catch (e) { setError(e instanceof Error ? e.message : "Không rút được"); } finally { setBusy(""); }
      }} className="rounded-full border border-line px-4 py-2 text-sm">Rút hồ sơ</button>}
    </article>)}
  </div>;
}
