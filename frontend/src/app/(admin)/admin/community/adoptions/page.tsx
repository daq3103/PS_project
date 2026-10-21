"use client";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api, type AdoptionRequestAdminOut } from "@/lib/api-client";
import { adoptionLabels } from "@/components/community/labels";
import { CommunityAdminNav } from "@/components/community/AdminNav";

export default function Page() {
  const [rows, setRows] = useState<AdoptionRequestAdminOut[]>([]);
  const [status, setStatus] = useState("");
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState("");
  const load = useCallback(async () => {
    setLoading(true);
    try { setRows(await api.adminAdoptionRequests(status, offset)); setError(""); }
    catch (e) { setError(e instanceof Error ? e.message : "Không tải được hồ sơ"); }
    finally { setLoading(false); }
  }, [status, offset]);
  useEffect(() => { void load(); }, [load]);
  async function action(row: AdoptionRequestAdminOut, value: "contact" | "approve" | "reject" | "complete", form: HTMLFormElement) {
    if (busy) return;
    if (value === "complete" && !window.confirm("Xác nhận bé đã được bàn giao thực tế? Các hồ sơ còn lại sẽ kết thúc.")) return;
    const data = new FormData(form);
    setBusy(row.id); setError("");
    try { await api.adminAdoptionAction(row.id, value, String(data.get("reason") || "") || undefined, String(data.get("admin_note") || "")); await load(); }
    catch (e) { setError(e instanceof Error ? e.message : "Thao tác thất bại"); }
    finally { setBusy(""); }
  }
  return <div className="space-y-4"><CommunityAdminNav /><h1 className="font-display text-2xl text-forest">Hồ sơ nhận nuôi</h1>
    <label className="block text-sm">Trạng thái<select value={status} onChange={e => { setStatus(e.target.value); setOffset(0); }} className="ml-3 rounded-sm border border-line p-2"><option value="">Tất cả</option>{Object.entries(adoptionLabels).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>
    {error && <p role="alert" className="text-danger">{error}</p>}{loading ? <p>Đang tải…</p> : !rows.length && <p>Chưa có hồ sơ phù hợp.</p>}
    {!loading && rows.map(row => <article key={row.id} className="space-y-3 rounded-sm border border-line bg-surface p-5">
      <div className="flex flex-wrap justify-between gap-2"><Link href={`/tram-cuu-ho/${row.post_slug}`} className="font-display text-xl text-forest">{row.post_title}</Link><span>{adoptionLabels[row.status]}</span></div>
      <p>{row.applicant_name} · {row.applicant_phone}</p><p className="whitespace-pre-wrap">Địa chỉ: {row.applicant_address}</p><p className="whitespace-pre-wrap">Điều kiện sống: {row.living_condition}</p>
      {row.outcome_reason && <p>Kết quả: {row.outcome_reason}</p>}
      {["pending", "contacted", "approved"].includes(row.status) && <form className="space-y-3" onSubmit={e => e.preventDefault()}>
        <label className="block text-sm">Ghi chú nội bộ<textarea name="admin_note" maxLength={1000} defaultValue={row.admin_note ?? ""} className="mt-1 w-full rounded-sm border border-line p-2" /></label>
        <label className="block text-sm">Lý do / kết quả thông báo cho người đăng ký<input name="reason" maxLength={500} className="mt-1 w-full rounded-sm border border-line p-2" /></label>
        <div className="flex flex-wrap gap-2">{([
          ...(row.status === "pending" ? [["contact", "Đã liên hệ"]] : []),
          ...(row.status === "contacted" ? [["approve", "Chọn người nhận"]] : []),
          ...(row.status === "approved" ? [["complete", "Xác nhận bàn giao"]] : []), ["reject", "Từ chối"],
        ] as ["contact" | "approve" | "reject" | "complete", string][]).map(([value, label]) => <button key={value} type="button" disabled={!!busy} onClick={e => void action(row, value, e.currentTarget.form!)} className="rounded-full border border-line px-4 py-2 text-sm disabled:opacity-50">{busy === row.id ? "Đang xử lý…" : label}</button>)}</div>
      </form>}
    </article>)}
    <div className="flex gap-3"><button disabled={!offset || loading} onClick={() => setOffset(v => Math.max(0, v - 100))} className="rounded-full border p-2 disabled:opacity-40">Trang trước</button><button disabled={rows.length < 100 || loading} onClick={() => setOffset(v => v + 100)} className="rounded-full border p-2 disabled:opacity-40">Trang sau</button></div>
  </div>;
}
