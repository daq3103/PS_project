"use client";

import { useCallback, useContext, useEffect, useState } from "react";
import { api, type ShopExpense, type ShopOverview as Overview } from "@/lib/api-client";
import { AdminUserContext } from "./AdminUserContext";
import { canManagePlatform } from "@/lib/admin-navigation";
import { formatVnd } from "@/lib/format";

const expenseLabels = { shipping: "Phí vận chuyển", supplies: "Mua vật tư", other: "Chi phí khác" };
const dayLabel = (day: string) => new Date(`${day}T12:00:00+07:00`).toLocaleDateString("vi-VN", { day: "2-digit", month: "2-digit", timeZone: "Asia/Ho_Chi_Minh" });

export function ShopOverview() {
  const user = useContext(AdminUserContext);
  const canEdit = canManagePlatform(user);
  const [overview, setOverview] = useState<Overview | null>(null);
  const [expenses, setExpenses] = useState<ShopExpense[]>([]);
  const [mode, setMode] = useState<"revenue" | "orders">("revenue");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [spentOn, setSpentOn] = useState(() => new Date().toLocaleDateString("en-CA", { timeZone: "Asia/Ho_Chi_Minh" }));
  const [category, setCategory] = useState<"shipping" | "supplies" | "other">("supplies");
  const [amount, setAmount] = useState("");
  const [note, setNote] = useState("");
  const [reference, setReference] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const load = useCallback(async () => {
    try {
      const [summary, rows] = await Promise.all([api.shopOverview(), api.shopExpenses()]);
      setOverview(summary); setExpenses(rows); setError("");
    } catch (e) { setError(e instanceof Error ? e.message : "Không tải được số liệu Shop."); }
  }, []);
  useEffect(() => { void load(); }, [load]);

  async function upload(id: string, receipt: File) {
    const body = new FormData(); body.set("file", receipt);
    await api.addShopExpenseReceipt(id, body);
  }

  async function createExpense(event: React.FormEvent) {
    event.preventDefault(); setBusy(true); setError("");
    try {
      if (!note.trim() || !Number.isInteger(Number(amount)) || Number(amount) <= 0) throw new Error("Ghi rõ khoản chi và số tiền hợp lệ.");
      const created = await api.createShopExpense({ spent_on: spentOn, category, amount: Number(amount), note: note.trim(), reference: reference.trim() || null });
      setAmount(""); setNote(""); setReference(""); setFile(null);
      let uploadError = "";
      if (file) {
        try { await upload(created.id, file); }
        catch (e) { uploadError = `Đã lưu khoản chi; ảnh chưa tải được. Hãy gửi lại bên dưới. ${e instanceof Error ? e.message : ""}`; }
      }
      await load();
      if (uploadError) setError(uploadError);
    } catch (e) { setError(e instanceof Error ? e.message : "Không ghi được khoản chi."); }
    finally { setBusy(false); }
  }

  async function voidExpense(row: ShopExpense) {
    const reason = window.prompt(`Lý do hủy khoản chi “${row.note}” (lịch sử và ảnh vẫn được giữ):`);
    if (reason === null) return;
    if (reason.trim().length < 5) { setError("Lý do hủy cần ít nhất 5 ký tự."); return; }
    setBusy(true);
    try { await api.voidShopExpense(row.id, reason.trim()); await load(); }
    catch (e) { setError(e instanceof Error ? e.message : "Không hủy được khoản chi."); }
    finally { setBusy(false); }
  }

  const max = Math.max(1, ...(overview?.daily.flatMap(d => mode === "revenue"
    ? [d.revenue, d.product_cost + d.carrier_shipping_cost + d.other_expenses]
    : [d.orders]) ?? []));
  const progress = overview?.orders_by_progress;
  const progressTotal = (progress?.completed ?? 0) + (progress?.pending ?? 0) + (progress?.cancelled_or_returned ?? 0);
  const incompleteCosts = overview?.daily.some(d => d.missing_product_cost_orders || d.missing_shipping_cost_orders);

  return <section className="space-y-7" aria-label="Tình hình Shop 7 ngày">
    <div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="font-display text-2xl text-forest">7 ngày gần nhất</h2><p className="text-sm text-ink-muted">{overview?.basis}</p></div><button type="button" onClick={() => void load()} className="rounded-full border border-forest px-4 py-2 text-sm text-forest">Làm mới</button></div>
    {error && <p role="alert" className="rounded-lg border border-danger/30 p-3 text-sm text-danger">{error}</p>}
    {overview && <>
      <div className="rounded-xl border border-line bg-surface p-4"><div className="flex flex-wrap items-center justify-between gap-3"><h3 className="font-semibold">Doanh thu / số đơn theo ngày</h3><div className="flex gap-2"><button type="button" aria-pressed={mode === "revenue"} onClick={() => setMode("revenue")} className={`rounded-full border px-3 py-1 text-sm ${mode === "revenue" ? "bg-forest text-white" : "text-forest"}`}>Doanh thu</button><button type="button" aria-pressed={mode === "orders"} onClick={() => setMode("orders")} className={`rounded-full border px-3 py-1 text-sm ${mode === "orders" ? "bg-forest text-white" : "text-forest"}`}>Số đơn</button></div></div>
        <p className="mt-2 text-xs text-ink-muted">Doanh thu tính theo ngày giao thành công; số đơn tính theo ngày đặt.</p>
        {mode === "revenue" && <p className="mt-2 flex flex-wrap gap-4 text-xs"><span><i className="mr-1 inline-block h-3 w-3 rounded-sm bg-forest"/>Doanh thu</span><span><i className="mr-1 inline-block h-3 w-3 rounded-sm bg-danger"/>Chi phí: giá vốn + phí ship + khoản chi đã ghi</span></p>}
        <div className="mt-5 flex h-56 items-end gap-2 border-b border-line pb-2">{overview.daily.map(d => { const value = mode === "revenue" ? d.revenue : d.orders; const cost = d.product_cost + d.carrier_shipping_cost + d.other_expenses; return <div key={d.day} className="flex min-w-0 flex-1 flex-col items-center justify-end gap-1"><div className="flex h-[180px] w-full items-end justify-center gap-1">{mode === "revenue" ? <><div className="flex h-full min-w-0 flex-1 flex-col items-center justify-end" title={`${dayLabel(d.day)} doanh thu ${formatVnd(value)}`}><span className="text-[10px] font-medium">{value ? `${Math.round(value / 1000)}k` : ""}</span><div className="w-full max-w-8 rounded-t bg-forest" style={{ height: `${value ? Math.max(8, value / max * 145) : 2}px` }} /></div><div className="flex h-full min-w-0 flex-1 flex-col items-center justify-end" title={`${dayLabel(d.day)} chi phí ${formatVnd(cost)}`}><span className="text-[10px] font-medium text-danger">{cost ? `${Math.round(cost / 1000)}k` : ""}</span><div className="w-full max-w-8 rounded-t bg-danger" style={{ height: `${cost ? Math.max(8, cost / max * 145) : 2}px` }} /></div></> : <div className="flex h-full w-full flex-col items-center justify-end" title={`${dayLabel(d.day)}: ${value} đơn`}><span className="text-[10px] font-medium">{value}</span><div className="w-full max-w-14 rounded-t bg-forest" style={{ height: `${value ? Math.max(8, value / max * 145) : 2}px` }} /></div>}</div><span className="text-[10px] text-ink-muted sm:text-xs">{dayLabel(d.day)}</span></div>; })}</div>
        <p className="mt-2 text-sm">Lãi tạm tính hôm nay: <strong className={overview.daily[6].estimated_profit < 0 ? "text-danger" : "text-forest"}>{formatVnd(overview.daily[6].estimated_profit)}</strong></p>
      </div>
      <div className="rounded-xl border border-line bg-surface p-4"><h3 className="font-semibold">Tình trạng các đơn đặt trong 7 ngày</h3><div className="mt-4 flex h-8 overflow-hidden rounded-full bg-line" aria-label={`Hoàn tất ${progress?.completed ?? 0}, đang xử lý ${progress?.pending ?? 0}, hủy hoặc hoàn ${progress?.cancelled_or_returned ?? 0}`}>{progressTotal > 0 && <><div style={{width:`${(progress?.completed ?? 0) / progressTotal * 100}%`}} className="bg-forest"/><div style={{width:`${(progress?.pending ?? 0) / progressTotal * 100}%`}} className="bg-honey"/><div style={{width:`${(progress?.cancelled_or_returned ?? 0) / progressTotal * 100}%`}} className="bg-danger/70"/></>}</div><div className="mt-3 flex flex-wrap gap-4 text-sm"><span>🟢 Đã giao: {progress?.completed ?? 0}</span><span>🟡 Đang xử lý: {progress?.pending ?? 0}</span><span>🔴 Hủy/hoàn: {progress?.cancelled_or_returned ?? 0}</span></div></div>
      <div className="rounded-xl border border-line bg-surface p-4"><h3 className="font-semibold">Lãi tạm tính theo ngày</h3><p className="mt-1 text-xs text-ink-muted">Doanh thu đơn đã giao − giá vốn theo lô − phí hãng đã ghi − chi phí Shop đã nhập. Đây chưa phải tiền thực nhận hoặc lãi đã chốt.</p>{incompleteCosts && <p className="mt-2 text-sm text-honey">Có đơn thiếu giá vốn hoặc phí vận chuyển thực tế; số lãi có thể cao hơn thực tế.</p>}<div className="mt-4 overflow-x-auto"><table className="w-full min-w-[620px] text-sm"><thead><tr className="border-b text-left text-ink-muted"><th className="p-2">Ngày</th><th className="p-2 text-right">Đã giao</th><th className="p-2 text-right">Doanh thu</th><th className="p-2 text-right">Giá vốn</th><th className="p-2 text-right">Phí hãng</th><th className="p-2 text-right">Chi khác</th><th className="p-2 text-right">Lãi tạm tính</th></tr></thead><tbody>{overview.daily.map(d => <tr key={d.day} className="border-b border-line"><td className="p-2">{dayLabel(d.day)}</td><td className="p-2 text-right">{d.delivered_orders}</td><td className="p-2 text-right">{formatVnd(d.revenue)}</td><td className="p-2 text-right">{formatVnd(d.product_cost)}</td><td className="p-2 text-right">{formatVnd(d.carrier_shipping_cost)}</td><td className="p-2 text-right">{formatVnd(d.other_expenses)}</td><td className={`p-2 text-right font-semibold ${d.estimated_profit < 0 ? "text-danger" : "text-forest"}`}>{formatVnd(d.estimated_profit)}{d.missing_product_cost_orders || d.missing_shipping_cost_orders ? " *" : ""}</td></tr>)}</tbody></table></div><p className="mt-2 text-xs text-ink-muted">* Cần bổ sung giá vốn hoặc phí hãng để đối chiếu chính xác.</p></div>
    </>}
    <div className="space-y-4 rounded-xl border border-line bg-surface p-4"><div><h3 className="font-semibold">Sổ chi phí Shop và chứng từ</h3><p className="text-xs text-ink-muted">Ghi chú người chi, mục đích và mã chứng từ. Phí ship chỉ nhập ở đây nếu chưa được ghi từ vận đơn để tránh trừ hai lần. Ảnh chỉ người có quyền quản trị Shop xem được. Khoản hủy vẫn nằm trong lịch sử.</p></div>
      {canEdit && <form onSubmit={createExpense} className="grid gap-3 sm:grid-cols-2"><label className="text-sm">Ngày chi<input type="date" required value={spentOn} onChange={e => setSpentOn(e.target.value)} className="mt-1 block w-full rounded border border-line p-2" /></label><label className="text-sm">Loại chi<select value={category} onChange={e => setCategory(e.target.value as typeof category)} className="mt-1 block w-full rounded border border-line p-2">{Object.entries(expenseLabels).map(([key,label]) => <option key={key} value={key}>{label}</option>)}</select></label><label className="text-sm">Số tiền (đ)<input type="number" min="1" step="1" required value={amount} onChange={e => setAmount(e.target.value)} className="mt-1 block w-full rounded border border-line p-2" /></label><label className="text-sm">Mã đơn / giao dịch (nếu có)<input value={reference} maxLength={150} onChange={e => setReference(e.target.value)} className="mt-1 block w-full rounded border border-line p-2" /></label><label className="text-sm sm:col-span-2">Ghi chú khoản chi<textarea required minLength={3} maxLength={2000} value={note} onChange={e => setNote(e.target.value)} placeholder="Ai mua, mua gì, vì sao, cho đơn nào…" className="mt-1 block w-full rounded border border-line p-2" /></label><label className="text-sm sm:col-span-2">Ảnh hóa đơn hoặc chuyển khoản (có thể thêm sau)<input type="file" accept="image/jpeg,image/png,image/webp" onChange={e => setFile(e.target.files?.[0] ?? null)} className="mt-1 block w-full text-sm" /></label><button disabled={busy} className="rounded-full bg-forest px-4 py-2 text-sm text-white disabled:opacity-50">{busy ? "Đang lưu…" : "Ghi khoản chi"}</button></form>}
      <div className="space-y-3">{expenses.length === 0 && <p className="text-sm text-ink-muted">Chưa có khoản chi nào được ghi.</p>}{expenses.map(row => <article key={row.id} className={`rounded-lg border border-line p-3 text-sm ${row.voided_at ? "opacity-60" : ""}`}><div className="flex flex-wrap justify-between gap-2"><strong>{expenseLabels[row.category]} · {formatVnd(row.amount)}</strong><span>{dayLabel(row.spent_on)} · {row.voided_at ? "Đã hủy ghi nhận" : "Có hiệu lực"}</span></div><p className="mt-1 whitespace-pre-wrap">{row.note}</p><p className="text-xs text-ink-muted">Người ghi: {row.actor_name || row.actor_user_id.slice(0, 8)} · {new Date(row.created_at).toLocaleString("vi-VN")}{row.reference ? ` · Mã ${row.reference}` : ""}</p>{row.void_reason && <p className="text-xs text-danger">Lý do hủy: {row.void_reason}{row.voided_by_name ? ` · ${row.voided_by_name}` : ""}</p>}<div className="mt-2 flex flex-wrap items-center gap-3">{row.receipts.map((receipt, index) => <a key={receipt.id} href={`/api/proxy/api/v1/admin/shop-expenses/${row.id}/receipts/${receipt.id}`} target="_blank" rel="noopener noreferrer" className="text-forest underline">Xem chứng từ {index + 1}</a>)}{canEdit && !row.voided_at && row.receipts.length < 5 && <label className="cursor-pointer text-forest underline">+ Thêm ảnh<input type="file" accept="image/jpeg,image/png,image/webp" className="sr-only" onChange={async e => { const file = e.target.files?.[0]; if (!file) return; try { await upload(row.id, file); await load(); } catch (err) { setError(err instanceof Error ? err.message : "Không tải được ảnh."); } }} /></label>}{canEdit && !row.voided_at && <button type="button" disabled={busy} onClick={() => void voidExpense(row)} className="text-danger underline">Hủy ghi nhận</button>}</div></article>)}</div>
    </div>
  </section>;
}
