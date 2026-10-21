"use client";
import { useState } from "react";
import { api } from "@/lib/api-client";

export function ReportForm({ postId }: { postId: string }) {
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  return <details className="mt-6 border-t border-line pt-4"><summary className="cursor-pointer text-sm text-ink-muted">Báo cáo tin không phù hợp</summary>
    <form className="mt-3 space-y-3" onSubmit={async e => {
      e.preventDefault(); setBusy(true);
      const reason = String(new FormData(e.currentTarget).get("reason"));
      try { await api.reportCommunityPost(postId, reason); setMessage("Đã gửi báo cáo cho người quản trị."); }
      catch (e) { setMessage(e instanceof Error ? e.message : "Không gửi được báo cáo"); }
      finally { setBusy(false); }
    }}><label className="block text-sm">Lý do<textarea name="reason" required minLength={10} maxLength={1000} className="mt-1 w-full rounded-sm border border-line p-2" /></label>
      <button disabled={busy} className="rounded-full border border-line px-4 py-2 text-sm">Gửi báo cáo</button><p role="status">{message}</p>
    </form></details>;
}
