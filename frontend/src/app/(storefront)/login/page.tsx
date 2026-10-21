"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { api } from "@/lib/api-client";

export default function LoginPage() {
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    void api.me();
  }, []);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    setSuccess("");
    try {
      await api.me();
      const isEmail = identifier.includes("@");
      const payload = isEmail
        ? { password, email: identifier }
        : { password, phone: identifier };
      const user = await api.login(payload);
      const staffRoles = new Set(["owner", "warehouse_staff", "cskh_staff"]);
      const dest = staffRoles.has(user.role) ? "/admin" : "/account";
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
      <h1 className="font-display text-4xl font-semibold text-ink md:text-5xl">Đăng nhập</h1>
      <p className="mt-3 text-base text-ink-muted">
        Chưa có tài khoản?{" "}
        <Link
          href="/register"
          className="font-bold text-forest underline decoration-2 underline-offset-4 hover:text-forest-deep"
        >
          Đăng ký
        </Link>
      </p>
      <form onSubmit={onSubmit} className="mt-8 space-y-4">
        <Field label="Email hoặc số điện thoại" value={identifier} onChange={setIdentifier} required />
        <Field label="Mật khẩu" value={password} onChange={setPassword} type="password" required />
        {error && <p className="text-sm font-medium text-danger">{error}</p>}
        {success && (
          <p className="rounded-sm border border-forest/20 bg-forest/8 px-3 py-2 text-sm font-medium text-forest">
            {success}
          </p>
        )}
        <button
          type="submit"
          disabled={loading || !!success}
          className="w-full rounded-full bg-forest py-3.5 text-base font-bold tracking-wide text-white shadow-sm transition hover:bg-forest-deep disabled:opacity-60"
        >
          {success ? "Đang chuyển…" : loading ? "Đang đăng nhập…" : "Đăng nhập"}
        </button>
      </form>
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
