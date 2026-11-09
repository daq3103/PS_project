"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";
import { api } from "@/lib/api-client";

export function ResetPasswordForm({ token, verifiedByCode = false }: { token: string; verifiedByCode?: boolean }) {
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);
  const [loading, setLoading] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    if (password !== confirmation) {
      setError("Hai mật khẩu chưa khớp.");
      return;
    }
    setLoading(true);
    try {
      await api.confirmPasswordReset(token, password);
      if (!verifiedByCode) window.history.replaceState(null, "", "/reset-password");
      setSuccess(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Chưa đổi được mật khẩu. Vui lòng thử lại.");
    } finally {
      setLoading(false);
    }
  }

  return <div className="mx-auto max-w-lg rounded-3xl border border-line bg-surface p-6 shadow-sm md:p-9">
    <p className="text-sm font-semibold uppercase tracking-widest text-moss">Tài khoản PetHome</p>
    <h1 className="mt-3 font-display text-4xl text-forest">Đặt mật khẩu mới</h1>
    {success ? <div role="status" className="mt-6">
      <p className="rounded-xl border border-forest/20 bg-forest/5 p-4">Mật khẩu đã được đổi. Hãy đăng nhập lại trên các thiết bị của bạn.</p>
      <Link href="/login" className="mt-6 inline-block rounded-full bg-forest px-6 py-3 font-semibold text-white hover:bg-forest-deep">Đăng nhập</Link>
    </div> : !token ? <div className="mt-6 space-y-4">
      <p role="alert" className="text-ink-muted">Liên kết đặt lại mật khẩu chưa đầy đủ.</p>
      <Link href="/forgot-password" className="font-semibold text-forest underline">Yêu cầu liên kết mới</Link>
    </div> : <>
      <p className="mt-4 leading-relaxed text-ink-muted">{verifiedByCode ? "Email đã được xác minh. Đặt mật khẩu mới trong 10 phút; mật khẩu cần ít nhất 8 ký tự." : "Chọn mật khẩu mới có ít nhất 8 ký tự. Liên kết chỉ dùng được một lần."}</p>
      <form onSubmit={submit} className="mt-7 space-y-5">
        <label className="block text-sm font-semibold text-ink">Mật khẩu mới
          <input type="password" value={password} onChange={event => setPassword(event.target.value)} required minLength={8} maxLength={128} autoComplete="new-password" className="mt-2 w-full rounded-xl border border-line bg-paper px-4 py-3 font-normal outline-none focus:border-forest" />
        </label>
        <label className="block text-sm font-semibold text-ink">Nhập lại mật khẩu mới
          <input type="password" value={confirmation} onChange={event => setConfirmation(event.target.value)} required minLength={8} maxLength={128} autoComplete="new-password" className="mt-2 w-full rounded-xl border border-line bg-paper px-4 py-3 font-normal outline-none focus:border-forest" />
        </label>
        {error && <p role="alert" className="text-sm text-danger">{error}</p>}
        <button type="submit" disabled={loading} className="w-full rounded-full bg-forest px-5 py-3 font-semibold text-white hover:bg-forest-deep disabled:opacity-50">{loading ? "Đang đổi…" : "Lưu mật khẩu mới"}</button>
      </form>
      <a href="/forgot-password" className="mt-6 inline-block text-sm font-semibold text-forest hover:underline">Yêu cầu mã mới</a>
    </>}
  </div>;
}
