"use client";

import Link from "next/link";
import { GoogleSignIn } from "@/components/GoogleSignIn";
import { FormEvent, useEffect, useState } from "react";
import { api, refreshSession } from "@/lib/api-client";

export default function LoginPage() {
  const nextPath = () => { const value = new URLSearchParams(window.location.search).get("next"); return value?.startsWith("/") && !value.startsWith("//") ? value : null; };
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [loading, setLoading] = useState(false);
  const [needsCode, setNeedsCode] = useState(false);
  const [code, setCode] = useState("");
  const [checkingSession, setCheckingSession] = useState(true);
  const [needsVerification, setNeedsVerification] = useState(false);

  useEffect(() => {
    let active = true;
    void (async () => {
      try {
        if (new URLSearchParams(window.location.search).get("resume") === "1") await refreshSession();
        const { user, admin_verified } = await api.me();
        if (!active) return;
        if (user && !(user.role === "owner" && user.totp_enabled && !admin_verified)) {
          window.location.replace(nextPath() ?? (user.role === "owner" && !user.totp_enabled ? "/admin/settings" : user.role === "owner" || user.staff_permissions?.length ? "/admin" : "/account"));
          return;
        }
        if (user?.role === "owner" && user.totp_enabled && !admin_verified) setNeedsVerification(true);
      } catch {
        // Expired sessions show the sign-in form.
      }
      if (active) setCheckingSession(false);
    })();
    return () => { active = false; };
  }, []);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    if (!identifier.trim() || !password) {
      setError(!identifier.trim() ? "Vui lòng nhập tên tài khoản." : "Vui lòng nhập mật khẩu.");
      return;
    }
    setLoading(true);
    setError("");
    setSuccess("");
    try {
      const contact = identifier.trim();
      const isEmail = contact.includes("@");
      const payload = isEmail
        ? { password, email: contact, totp_code: needsCode ? code : undefined }
        : /^0[0-9]{9,10}$/.test(contact) ? { password, phone: contact, totp_code: needsCode ? code : undefined }
        : { password, username: contact, totp_code: needsCode ? code : undefined };
      const user = await api.login(payload);
      if ("requires_totp" in user) {
        setNeedsCode(true); setCode(""); setLoading(false);
        return;
      }
      const dest = nextPath() ?? (user.role === "owner" && !user.totp_enabled ? "/admin/settings" : user.role === "owner" || user.staff_permissions?.length ? "/admin" : "/account");
      setSuccess(`Đăng nhập thành công. Xin chào ${user.full_name}…`);
      window.dispatchEvent(new Event("petshop:auth"));
      // Full navigation so header remounts with session cookies
      window.setTimeout(() => {
        window.location.assign(dest);
      }, 600);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Đăng nhập thất bại");
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto max-w-md">
      {checkingSession ? <p role="status" className="py-12 text-center text-ink-muted">Đang kiểm tra phiên đăng nhập…</p> : <>
      <h1 className="font-display text-4xl font-semibold text-ink md:text-5xl">Đăng nhập</h1>
      {needsVerification && <p className="mt-3 rounded-lg border border-honey/40 bg-honey/10 p-3 text-sm">Phiên quản trị cần xác minh lại. Đăng nhập và nhập mã xác thực để tiếp tục.</p>}
      <p className="mt-3 text-base text-ink-muted">
        Chưa có tài khoản?{" "}
        <Link
          href="/register"
          className="font-bold text-forest underline decoration-2 underline-offset-4 hover:text-forest-deep"
        >
          Đăng ký
        </Link>
      </p>
      <GoogleSignIn />
      <p className="mt-4 text-xs text-ink-muted">Tài khoản cũ vẫn có thể dùng email hoặc số điện thoại để đăng nhập.</p>
      <form noValidate onSubmit={onSubmit} className="mt-8 space-y-4">
        {!needsCode ? <>
          <Field label="Tên tài khoản" value={identifier} onChange={setIdentifier} required />
          <Field label="Mật khẩu" value={password} onChange={setPassword} type="password" required />
        </> : <div className="space-y-4">
          <p className="text-sm text-ink-muted">Tài khoản quản trị viên cần xác minh hai bước. Nhập mã từ ứng dụng xác thực; bạn sẽ không phải nhập lại khi thao tác trong phiên này.</p>
          <label className="block text-sm font-semibold">Mã xác thực 6 số
            <input autoFocus inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{6}" maxLength={6} required value={code} onChange={e => setCode(e.target.value.replace(/\D/g, ""))} className="mt-2 block w-full rounded-sm border border-line bg-surface px-3 py-3 text-center text-lg tracking-widest" />
          </label>
          <button type="button" disabled={loading} onClick={() => { setNeedsCode(false); setCode(""); setError(""); }} className="text-sm text-forest underline">Quay lại nhập tài khoản</button>
        </div>}
        <div className="text-right text-sm"><Link href="/forgot-password" className="font-semibold text-forest hover:underline">Quên mật khẩu?</Link></div>
        {error && <p role="alert" className="text-sm font-medium text-danger">{error}</p>}
        {success && (
          <p className="rounded-sm border border-forest/20 bg-forest/8 px-3 py-2 text-sm font-medium text-forest">
            {success}
          </p>
        )}
        <button
          type="submit"
          disabled={loading || !!success || (needsCode && code.length !== 6)}
          className="w-full rounded-full bg-forest py-3.5 text-base font-bold tracking-wide text-white shadow-sm transition hover:bg-forest-deep disabled:opacity-60"
        >
          {success ? "Đang chuyển…" : loading ? "Đang đăng nhập…" : needsCode ? "Xác minh và đăng nhập" : "Đăng nhập"}
        </button>
      </form>
      </>}
    </div>
  );
}

function Field({
  label,
  value,
  onChange,
  type = "text",
  required,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  type?: string;
  required?: boolean;
}) {
  return (
    <label className="block text-sm">
      <span className="font-semibold text-ink">{label}</span>
      <input
        type={type}
        value={value}
        required={required}
        onChange={(e) => onChange(e.target.value)}
        className="mt-1.5 w-full rounded-sm border border-line bg-surface px-3 py-2.5 outline-none focus:border-forest"
      />
    </label>
  );
}
