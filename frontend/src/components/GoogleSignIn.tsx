"use client";
import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api-client";

type GoogleIdentity = { initialize: (options: Record<string, unknown>) => void; renderButton: (element: HTMLElement, options: Record<string, unknown>) => void };
declare global { interface Window { google?: { accounts: { id: GoogleIdentity } } } }

export function GoogleSignIn({ link = false, onLinked }: { link?: boolean; onLinked?: () => void }) {
  const target = useRef<HTMLDivElement>(null);
  const [error, setError] = useState("");
  const [available, setAvailable] = useState<boolean | null>(null);
  const [credential, setCredential] = useState("");
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(token: string, totp?: string) {
    setBusy(true); setError("");
    try {
      await api.me();
      const user = await api.googleLogin(token, link, totp);
      if ("requires_totp" in user) { setCredential(token); return; }
      window.dispatchEvent(new Event("petshop:auth"));
      if (link) { onLinked?.(); return; }
      const next = new URLSearchParams(window.location.search).get("next");
      window.location.assign(next?.startsWith("/") && !next.startsWith("//") ? next : user.role === "owner" && !user.totp_enabled ? "/admin/settings" : user.role === "owner" || user.staff_permissions?.length ? "/admin" : "/account");
    } catch (e) { setError(e instanceof Error ? e.message : "Chưa đăng nhập được Google."); }
    finally { setBusy(false); }
  }
  useEffect(() => {
    let active = true;
    void api.googleConfig().then(async config => {
      if (!active) return;
      setAvailable(Boolean(config.client_id));
      if (!config.client_id) return;
      if (!window.google) await new Promise<void>((resolve, reject) => {
        const script = document.createElement("script");
        script.src = "https://accounts.google.com/gsi/client";
        script.async = true; script.onload = () => resolve(); script.onerror = () => reject(new Error("Không tải được Google. Vui lòng thử lại."));
        document.head.appendChild(script);
      });
      if (!active || !target.current || !window.google) return;
      window.google.accounts.id.initialize({ client_id: config.client_id, nonce: config.nonce, auto_select: false,
        callback: (result: { credential: string }) => { void submit(result.credential); } });
      window.google.accounts.id.renderButton(target.current, { theme: "outline", size: "large", text: link ? "continue_with" : "signin_with", locale: "vi" });
    }).catch(e => { if (active) setError(e.message); });
    return () => { active = false; };
  // Config and callback are fixed for this mounted sign-in control.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [link]);
  return <section className="mt-6 space-y-3" aria-label={link ? "Liên kết Google" : "Đăng nhập Google"}>
    {link && <p className="font-semibold">Liên kết tài khoản Google</p>}
    <div ref={target} className={busy ? "pointer-events-none opacity-50" : ""} />
    {available === false && <p className="text-sm text-ink-muted">Đăng nhập Google chưa được bật.</p>}
    {credential && <form onSubmit={e => { e.preventDefault(); void submit(credential, code); }} className="space-y-3">
      <label className="block text-sm">Mã xác thực quản trị<input required inputMode="numeric" pattern="[0-9]{6}" maxLength={6} value={code} onChange={e => setCode(e.target.value)} className="mt-2 w-full rounded border p-3" /></label>
      <button disabled={busy} className="rounded-full bg-forest px-5 py-2 text-white">Xác minh</button>
    </form>}
    {error && <p role="alert" className="text-sm text-danger">{error}</p>}
  </section>;
}
