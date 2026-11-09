"use client";
import { ValidatedForm } from "@/components/ValidatedForm";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { api, type SupportTicket, type OrderOut } from "@/lib/api-client";

const STATUS: Record<string, string> = {open: "Đã tiếp nhận", in_progress: "Đang xử lý", waiting_customer: "Chờ bạn phản hồi", closed: "Đã đóng"};
const TOPIC: Record<string, string> = {order: "Đơn hàng", payment: "Thanh toán", return: "Đổi trả", other: "Khác"};
const field = "w-full rounded-xl border border-line bg-surface px-3 py-2 text-sm outline-none focus:border-forest";

export function SupportCenter({admin = false}: {admin?: boolean}) {
  const [tickets, setTickets] = useState<SupportTicket[]>([]);
  const [selected, setSelected] = useState<SupportTicket | null>(null);
  const [orders, setOrders] = useState<OrderOut[]>([]);
  const [subject, setSubject] = useState("");
  const [topic, setTopic] = useState("order");
  const [orderId, setOrderId] = useState("");
  const [content, setContent] = useState("");
  const [reply, setReply] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [signedIn, setSignedIn] = useState(true);
  const [offset, setOffset] = useState(0);
  const load = useCallback(async () => { setTickets(await api.listSupport(admin, offset)); }, [admin, offset]);
  useEffect(() => {
    let active = true;
    void (async () => {
      try {
        const me = await api.me();
        if (!active) return;
        if (!me.user) { setSignedIn(false); return; }
        await load();
        if (!admin) setOrders(await api.listMyOrders({limit: 100}));
      } catch (e) { if (active) setError(e instanceof Error ? e.message : "Không tải được yêu cầu hỗ trợ."); }
      finally { if (active) setLoading(false); }
    })();
    return () => { active = false; };
  }, [load, admin]);

  async function open(id: string) {
    setBusy(true); setError("");
    try { setSelected(await api.supportDetail(id)); setReply(""); }
    catch (e) { setError(e instanceof Error ? e.message : "Không mở được yêu cầu."); }
    finally { setBusy(false); }
  }
  async function create(e: FormEvent) {
    e.preventDefault(); setBusy(true); setError("");
    try {
      const ticket = await api.createSupport({subject, topic, content, order_id: orderId || undefined});
      setSubject(""); setContent("");
      await load(); setSelected(await api.supportDetail(ticket.id));
    } catch (e) { setError(e instanceof Error ? e.message : "Chưa gửi được yêu cầu."); }
    finally { setBusy(false); }
  }
  async function sendReply(e: FormEvent) {
    e.preventDefault(); if (!selected) return;
    setBusy(true); setError("");
    try { await api.replySupport(selected.id, reply); setReply(""); setSelected(await api.supportDetail(selected.id)); await load(); }
    catch (e) { setError(e instanceof Error ? e.message : "Chưa gửi được phản hồi."); }
    finally { setBusy(false); }
  }
  async function status(value: string) {
    if (!selected) return;
    setBusy(true); setError("");
    try { await api.supportStatus(selected.id, value); setSelected(await api.supportDetail(selected.id)); await load(); }
    catch (e) { setError(e instanceof Error ? e.message : "Chưa đổi được trạng thái."); }
    finally { setBusy(false); }
  }
  if (!signedIn) return <p>Vui lòng <Link href="/login?next=/account/support" className="text-forest underline">đăng nhập</Link> để gửi và theo dõi yêu cầu. Bạn cũng có thể dùng nút Liên hệ ở góc màn hình.</p>;
  return <div>
    <h1 className="font-display text-3xl text-forest">{admin ? "Yêu cầu hỗ trợ" : "Hỗ trợ khách hàng"}</h1>
    <p className="mt-2 text-sm leading-6 text-ink-muted">{admin ? "Tiếp nhận, trả lời và theo dõi tiến độ hỗ trợ khách." : "Gửi thắc mắc về đơn hàng, thanh toán hoặc đổi trả. Mọi phản hồi được lưu tại đây để bạn theo dõi."}</p>
    {error && <div role="alert" className="mt-4 flex flex-wrap items-center gap-3 rounded-xl bg-danger/10 p-3 text-sm text-danger"><span>{error}</span><button type="button" onClick={() => { setError(""); setLoading(true); void load().catch(e => setError(e instanceof Error ? e.message : "Không tải được yêu cầu hỗ trợ.")).finally(() => setLoading(false)); }} className="rounded-full border border-danger/30 px-3 py-1">Thử tải lại</button></div>}
    {loading ? <p className="mt-6 text-ink-muted">Đang tải yêu cầu…</p> : <div className="mt-6 grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.5fr)]">
      <div className="min-w-0 space-y-5">
        {!admin && <ValidatedForm onSubmit={create} className="space-y-3 rounded-2xl border border-line bg-surface p-5">
          <h2 className="font-semibold text-forest">Gửi yêu cầu mới</h2>
          <label className="block space-y-1 text-sm"><span>Tiêu đề</span><input required minLength={3} maxLength={150} value={subject} onChange={e => setSubject(e.target.value)} className={field} /></label>
          <label className="block space-y-1 text-sm"><span>Chủ đề</span><select value={topic} onChange={e => setTopic(e.target.value)} className={field}>{Object.entries(TOPIC).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>
          <label className="block space-y-1 text-sm"><span>Đơn hàng liên quan</span><select value={orderId} onChange={e => setOrderId(e.target.value)} className={field}><option value="">Không chọn đơn hàng</option>{orders.map(o => <option key={o.id} value={o.id}>{o.order_code}</option>)}</select></label>
          <label className="block space-y-1 text-sm"><span>Nội dung</span><textarea required minLength={10} maxLength={5000} rows={4} value={content} onChange={e => setContent(e.target.value)} className={field} /></label>
          <button disabled={busy} className="rounded-full bg-forest px-5 py-2 text-sm font-semibold text-white disabled:opacity-50">{busy ? "Đang gửi…" : "Gửi yêu cầu"}</button>
        </ValidatedForm>}
        <section aria-label="Danh sách yêu cầu" className="space-y-2"><h2 className="font-semibold text-forest">{admin ? "Danh sách tiếp nhận" : "Yêu cầu của bạn"}</h2>
          {!tickets.length && !error && <p className="py-4 text-sm text-ink-muted">Chưa có yêu cầu hỗ trợ.</p>}
          {tickets.map(t => <button key={t.id} disabled={busy} onClick={() => void open(t.id)} aria-pressed={selected?.id === t.id} className={`block w-full rounded-xl border p-4 text-left ${selected?.id === t.id ? "border-forest bg-moss/10" : "border-line bg-surface"}`}><span className="block break-words text-sm font-medium">{t.subject}</span><span className="mt-1 block text-xs text-ink-muted">{TOPIC[t.topic]} · {STATUS[t.status]}</span></button>)}
          <div className="flex justify-between text-sm"><button disabled={!offset || busy} onClick={() => setOffset(n => Math.max(0, n - 50))} className="text-forest disabled:opacity-30">Trang trước</button><button disabled={tickets.length < 50 || busy} onClick={() => setOffset(n => n + 50)} className="text-forest disabled:opacity-30">Trang sau</button></div>
        </section>
      </div>
      <section aria-label="Chi tiết yêu cầu" className="min-w-0 rounded-2xl border border-line bg-surface p-5">
        {!selected ? <p className="py-10 text-center text-sm text-ink-muted">Chọn một yêu cầu để xem phản hồi.</p> : <>
          <h2 className="break-words font-display text-2xl text-forest">{selected.subject}</h2><p className="mt-1 text-sm text-ink-muted">{STATUS[selected.status]}</p>
          {admin && <label className="mt-4 block text-sm">Trạng thái xử lý<select value={selected.status} disabled={busy} onChange={e => void status(e.target.value)} className={field}>{Object.entries(STATUS).map(([key, label]) => <option key={key} value={key}>{key === "waiting_customer" ? "Chờ khách phản hồi" : label}</option>)}</select></label>}
          <ol className="my-5 max-h-[32rem] space-y-3 overflow-y-auto" aria-label="Lịch sử trao đổi">{selected.messages?.map(m => <li key={m.id} className={`rounded-xl p-4 text-sm ${m.author_type === "staff" ? "bg-moss/10" : "bg-paper"}`}><p className="mb-2 text-xs font-semibold text-forest">{m.author_type === "staff" ? "Nhân viên PetHome" : m.author_type === "system" ? "Cập nhật yêu cầu" : "Khách hàng"} · {new Date(m.created_at).toLocaleString("vi-VN")}</p><p className="whitespace-pre-wrap break-words [overflow-wrap:anywhere]">{m.content}</p></li>)}</ol>
          {selected.status !== "closed" && <ValidatedForm onSubmit={sendReply} className="space-y-3"><label className="block space-y-1 text-sm"><span>Phản hồi</span><textarea required maxLength={5000} value={reply} onChange={e => setReply(e.target.value)} rows={3} className={field} /></label><button disabled={busy || !reply.trim()} className="rounded-full bg-forest px-5 py-2 text-sm font-semibold text-white disabled:opacity-50">Gửi phản hồi</button></ValidatedForm>}
        </>}
      </section>
    </div>}
  </div>;
}
