"use client";
import { ValidatedForm } from "@/components/ValidatedForm";

import Link from "next/link";
import { useEffect, useState, type FormEvent } from "react";
import { api } from "@/lib/api-client";
import { ResetPasswordForm } from "../reset-password/reset-password-form";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [available, setAvailable] = useState<boolean | null>(null);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);
  const [loading, setLoading] = useState(false);
  const [code, setCode] = useState("");
  const [token, setToken] = useState("");
  const [cooldown, setCooldown] = useState(0);

  useEffect(() => {
    void api.passwordResetConfig().then(result => setAvailable(result.available)).catch(() => setAvailable(false));
  }, []);

  useEffect(() => {
    if (cooldown <= 0) return;
    const timer = window.setTimeout(() => setCooldown(cooldown - 1), 1000);
    return () => window.clearTimeout(timer);
  }, [cooldown]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    setLoading(true);
    try {
      await api.requestPasswordReset(email.trim());
      setSuccess(true);
      setCode("");
      setCooldown(60);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Chưa gửi được yêu cầu. Vui lòng thử lại.");
    } finally {
      setLoading(false);
    }
  }

  async function verify(event: FormEvent) {
    event.preventDefault();
    setError("");
    setLoading(true);
    try {
      const result = await api.verifyPasswordResetCode(email.trim(), code);
      setToken(result.token);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Chưa xác minh được mã. Vui lòng thử lại.");
    } finally {
      setLoading(false);
    }
  }

  if (token) return <ResetPasswordForm token={token} verifiedByCode />;

  return <div className="mx-auto max-w-lg rounded-3xl border border-line bg-surface p-6 shadow-sm md:p-9">
    <p className="text-sm font-semibold uppercase tracking-widest text-moss">Tài khoản PetHome</p>
    <h1 className="mt-3 font-display text-4xl text-forest">Lấy lại mật khẩu</h1>
    {success ? <div className="mt-6 space-y-4">
      <p role="status" className="rounded-xl border border-forest/20 bg-forest/5 p-4 leading-relaxed">Nếu <strong>{email.trim()}</strong> thuộc tài khoản PetHome, mã 6 số sẽ được gửi đến hộp thư. Mã có hiệu lực 10 phút.</p>
      <ValidatedForm onSubmit={verify} className="space-y-5">
        <label className="block text-sm font-semibold text-ink">Mã xác minh
          <input autoFocus type="text" name="code" inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{6}" minLength={6} maxLength={6} value={code} onChange={event => setCode(event.target.value.replace(/[^0-9]/g, ""))} required placeholder="000000" className="mt-2 w-full rounded-xl border border-line bg-paper px-4 py-3 text-center text-2xl tracking-[.4em] outline-none focus:border-forest" />
        </label>
        {error && <p role="alert" className="text-sm text-danger">{error}</p>}
        <button type="submit" disabled={loading || code.length !== 6} className="w-full rounded-full bg-forest px-5 py-3 font-semibold text-white disabled:opacity-50">{loading ? "Đang xác minh…" : "Xác minh mã"}</button>
      </ValidatedForm>
      <p className="text-sm text-ink-muted">Chưa thấy mã? Kiểm tra thư rác. Mã mới sẽ thay thế mã cũ; mỗi mã được nhập tối đa 5 lần.</p>
      <ValidatedForm onSubmit={submit}><button type="submit" disabled={loading || cooldown > 0} className="text-sm font-semibold text-forest underline disabled:opacity-50">{cooldown > 0 ? `Gửi lại mã sau ${cooldown}s` : "Gửi lại mã"}</button></ValidatedForm>
      <button type="button" disabled={loading} onClick={() => { setSuccess(false); setError(""); setCode(""); }} className="text-sm font-semibold text-forest underline">Dùng email khác</button>
    </div> : <>
      <p className="mt-4 leading-relaxed text-ink-muted">Nhập email đã đăng ký. Chúng tôi sẽ gửi mã xác minh 6 số để bạn đặt mật khẩu mới.</p>
      {available === false && <p role="status" className="mt-6 rounded-xl border border-line bg-paper p-4 text-sm leading-relaxed">Gửi email lấy lại mật khẩu hiện chưa sẵn sàng. Vui lòng liên hệ người quản trị website để được hỗ trợ.</p>}
      <ValidatedForm onSubmit={submit} className="mt-7 space-y-5">
        <label className="block text-sm font-semibold text-ink">Email đăng ký
          <input type="email" name="email" value={email} onChange={event => setEmail(event.target.value)} required autoComplete="email" placeholder="tenban@example.com" className="mt-2 w-full rounded-xl border border-line bg-paper px-4 py-3 font-normal outline-none focus:border-forest" />
        </label>
        {error && <p role="alert" className="text-sm text-danger">{error}</p>}
        <button type="submit" disabled={loading || available !== true} className="w-full rounded-full bg-forest px-5 py-3 font-semibold text-white hover:bg-forest-deep disabled:opacity-50">{loading ? "Đang gửi…" : "Gửi mã xác minh"}</button>
      </ValidatedForm>
      <p className="mt-6 text-sm text-ink-muted">Chưa thêm email khôi phục? Đăng nhập rồi bổ sung email trong Hồ sơ. Nếu đã quên mật khẩu, vui lòng liên hệ người quản trị.</p>
    </>}
    <Link href="/login" className="mt-8 inline-block text-sm font-semibold text-forest hover:underline">← Quay lại đăng nhập</Link>
  </div>;
}
