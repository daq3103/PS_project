"use client";
import { FormEvent, useEffect, useState } from "react";
import { api, type OperationsReport } from "@/lib/api-client";
import { formatVnd } from "@/lib/format";

const TASK: Record<string, string> = {send_order_confirmation_email: "Gửi email xác nhận đơn", create_vietqr_payment: "Chuẩn bị thanh toán", create_shipment: "Tạo vận đơn"};
const KIND: Record<string, string> = {refund_required: "Cần hoàn tiền", overpayment: "Khách thanh toán dư"};
export default function OperationsPage() {
  const [report, setReport] = useState<OperationsReport | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [caseId, setCaseId] = useState("");
  const [reference, setReference] = useState("");
  const [note, setNote] = useState("");
  const [ack, setAck] = useState(false);
  async function load() { setReport(await api.operations()); }
  useEffect(() => { load().catch(e => setError(e.message)); }, []);
  async function retry(id: string) {
    setBusy(true); setError("");
    try { await api.retryOperation(id); await load(); }
    catch (e) { setError(e instanceof Error ? e.message : "Chưa chạy lại được công việc."); }
    finally { setBusy(false); }
  }
  async function resolve(e: FormEvent) {
    e.preventDefault(); setBusy(true); setError("");
    try { await api.resolveOperation(caseId, reference, note); setCaseId(""); setReference(""); setNote(""); setAck(false); await load(); }
    catch (e) { setError(e instanceof Error ? e.message : "Chưa ghi nhận được kết quả."); }
    finally { setBusy(false); }
  }
  return <div className="max-w-5xl space-y-6">
    <div><h1 className="font-display text-3xl text-forest">Việc cần xử lý</h1><p className="mt-2 text-sm text-ink-muted">Theo dõi tiền cần đối chiếu và các công việc chưa hoàn tất. Công việc lỗi vẫn được lưu để kiểm tra và thử lại.</p></div>
    {error && <p role="alert" className="text-sm text-danger">{error}</p>}
    {!report ? <p>Đang tải…</p> : <>
      <section className="rounded-2xl border border-line bg-surface p-5"><h2 className="font-display text-2xl text-forest">Tiền cần đối chiếu</h2>
        {!report.cases.length && <p className="mt-3 text-sm text-ink-muted">Không có khoản chờ xử lý.</p>}
        <ul className="mt-3 divide-y divide-line">{report.cases.map(c => <li key={c.id} className="flex flex-wrap items-center justify-between gap-3 py-4 text-sm"><div><p className="font-semibold">{c.order_code} · {KIND[c.kind] ?? "Cần kiểm tra"}</p><p className="text-ink-muted">{formatVnd(c.amount)} · {new Date(c.created_at).toLocaleString("vi-VN")}</p></div><button disabled={busy} onClick={() => {setCaseId(c.id); setAck(false);}} className="rounded-full border border-forest px-4 py-2 text-forest">Ghi nhận xử lý</button></li>)}</ul>
        {caseId && <form onSubmit={resolve} className="mt-4 space-y-3 rounded-xl bg-paper p-4"><h3 className="font-semibold">Ghi nhận chứng từ đã xử lý</h3><p className="text-sm text-ink-muted">Thực hiện hoàn hoặc đối soát qua ngân hàng trước, rồi lưu mã giao dịch và nội dung bên dưới. Thao tác này lưu kết quả xử lý, không tự chuyển tiền.</p><label className="block text-sm">Mã chứng từ<input required minLength={6} maxLength={150} value={reference} onChange={e => setReference(e.target.value)} className="mt-1 block w-full rounded-lg border border-line p-2" /></label><label className="block text-sm">Nội dung xử lý<textarea required minLength={10} maxLength={2000} value={note} onChange={e => setNote(e.target.value)} className="mt-1 block w-full rounded-lg border border-line p-2" /></label><label className="flex items-start gap-2 text-sm"><input type="checkbox" checked={ack} onChange={e => setAck(e.target.checked)} className="mt-1" />Tôi đã kiểm tra khoản tiền và chứng từ thực tế.</label><div className="flex gap-3"><button disabled={busy || !ack} className="rounded-full bg-forest px-4 py-2 text-sm text-white disabled:opacity-40">Lưu kết quả</button><button type="button" onClick={() => setCaseId("")} className="text-sm text-ink-muted">Hủy</button></div></form>}
      </section>
      <section className="rounded-2xl border border-line bg-surface p-5"><div className="flex items-center justify-between"><h2 className="font-display text-2xl text-forest">Công việc đang chờ</h2><button disabled={busy} onClick={() => void load().catch(e => setError(e.message))} className="text-sm text-forest">Làm mới</button></div>
        {!report.jobs.length && <p className="mt-3 text-sm text-ink-muted">Các công việc đã hoàn tất.</p>}
        <ul className="mt-3 divide-y divide-line">{report.jobs.map(j => <li key={j.id} className="flex flex-wrap items-center justify-between gap-3 py-4 text-sm"><div><p className="font-semibold">{TASK[j.task] ?? "Công việc hệ thống"}</p><p className="text-ink-muted">{j.status === "failed" ? "Cần kiểm tra cấu hình hoặc dịch vụ" : j.status === "running" ? "Đang xử lý" : "Đang chờ thử lại"} · Đã thử {j.attempts} lần</p></div>{j.status === "failed" && <button disabled={busy} onClick={() => void retry(j.id)} className="rounded-full border border-forest px-4 py-2 text-forest">Thử lại</button>}</li>)}</ul>
      </section>
    </>}
  </div>;
}
