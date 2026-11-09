"use client";
import { useState } from "react";
import { api } from "@/lib/api-client";
export function RecoveryEmail({ current, verified, onSaved }: { current: string | null; verified?: boolean; onSaved: () => void }) {
  const [email, setEmail] = useState(current || "");
  const [sentTo, setSentTo] = useState("");
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  return <section className="mt-6 rounded-xl border border-line p-4">
    <h2 className="font-semibold">Email khôi phục</h2>
    <p className="mt-2 text-sm text-ink-muted">{verified ? `Đã xác minh: ${current}` : "Thêm và xác minh email để lấy lại mật khẩu khi cần."}</p>
    <form className="mt-3 space-y-3" onSubmit={async e => {
      e.preventDefault(); setBusy(true); setMessage("");
      try {
        if (sentTo) { await api.verifyRecoveryEmail(sentTo, code); setSentTo(""); setMessage("Đã xác minh email."); onSaved(); }
        else { await api.requestRecoveryEmail(email); setSentTo(email); setMessage("Đã gửi mã 6 số. Mã có hiệu lực 10 phút."); }
      } catch (err) { setMessage(err instanceof Error ? err.message : "Chưa cập nhật được email."); }
      finally { setBusy(false); }
    }}>
      <label className="block text-sm">Email<input type="email" required value={email} disabled={!!sentTo || busy} onChange={e => setEmail(e.target.value)} className="mt-1 w-full rounded border border-line p-3" /></label>
      {sentTo && <label className="block text-sm">Mã xác minh email<input required autoComplete="one-time-code" inputMode="numeric" pattern="[0-9]{6}" maxLength={6} value={code} onChange={e => setCode(e.target.value)} className="mt-1 w-full rounded border border-line p-3" /></label>}
      <button disabled={busy} className="rounded-full bg-forest px-4 py-2 text-sm text-white">{busy ? "Đang xử lý…" : sentTo ? "Xác minh email" : "Gửi mã xác minh"}</button>
      {sentTo && <button type="button" disabled={busy} onClick={() => { setSentTo(""); setCode(""); }} className="ml-3 text-sm underline">Nhập lại email / gửi lại</button>}
      {message && <p role="status" className="text-sm">{message}</p>}
    </form>
  </section>;
}
