"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { api } from "@/lib/api-client";

export default function RegisterPage() {
  const router = useRouter();
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    void api.me();
  }, []);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      await api.me();
      if (password !== confirmPassword) {
        throw new Error("Mật khẩu xác nhận không khớp");
      }
      const isEmail = identifier.includes("@");
      await api.register({
        full_name: "Người dùng",
        password,
        email: isEmail ? identifier : undefined,
        phone: isEmail ? undefined : identifier,
      });
      router.push("/cart");
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Đăng ký thất bại");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto max-w-md">
      <h1 className="font-display text-4xl font-semibold text-ink md:text-5xl">Đăng ký</h1>
      <p className="mt-3 text-base text-ink-muted">
        Đã có tài khoản?{" "}
        <Link
          href="/login"
          className="font-bold text-forest underline decoration-2 underline-offset-4 hover:text-forest-deep"
        >
          Đăng nhập
        </Link>
      </p>
      <form onSubmit={onSubmit} className="mt-8 space-y-4">
        <label className="block text-sm">
          <span className="font-semibold text-ink">Email hoặc số điện thoại</span>
          <input
            required
            value={identifier}
            onChange={(e) => setIdentifier(e.target.value)}
            className="mt-1.5 w-full rounded-sm border border-line bg-surface px-3 py-2.5 outline-none focus:border-forest"
          />
        </label>
        <label className="block text-sm">
          <span className="font-semibold text-ink">Mật khẩu (≥ 8 ký tự)</span>
          <input
            type="password"
            required
            minLength={8}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="mt-1.5 w-full rounded-sm border border-line bg-surface px-3 py-2.5 outline-none focus:border-forest"
          />
        </label>
        <label className="block text-sm">
          <span className="font-semibold text-ink">Xác nhận mật khẩu</span>
          <input
            type="password"
            required
            minLength={8}
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            className="mt-1.5 w-full rounded-sm border border-line bg-surface px-3 py-2.5 outline-none focus:border-forest"
          />
        </label>
        {error && <p className="text-sm font-medium text-danger">{error}</p>}
        <button
          type="submit"
          disabled={loading}
          className="w-full rounded-full bg-forest py-3.5 text-base font-bold tracking-wide text-white shadow-sm transition hover:bg-forest-deep disabled:opacity-60"
        >
          {loading ? "Đang tạo…" : "Đăng ký"}
        </button>
      </form>
    </div>
  );
}
