"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api, type UserDto } from "@/lib/api-client";

export default function ProfilePage() {
  const router = useRouter();
  const [user, setUser] = useState<UserDto | null>(null);
  const [fullName, setFullName] = useState("");
  const [phone, setPhone] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  useEffect(() => {
    void (async () => {
      try {
        const me = await api.me();
        if (!me.user) {
          router.replace("/login");
          return;
        }
        setUser(me.user);
        setFullName(me.user.full_name);
        setPhone(me.user.phone ?? "");
      } catch {
        setError("Không tải được tài khoản");
      }
    })();
  }, [router]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError("");
    setSuccess("");
    try {
      const body: { full_name?: string; phone?: string } = {};
      if (fullName.trim()) body.full_name = fullName.trim();
      if (phone.trim()) body.phone = phone.trim();
      await api.updateProfile(body);
      const me = await api.me();
      if (me.user) setUser(me.user);
      window.dispatchEvent(new Event("petshop:auth"));
      setSuccess("Đã cập nhật hồ sơ.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Cập nhật thất bại");
    } finally {
      setSaving(false);
    }
  }

  if (!user) return <p className="text-ink-muted">Đang tải…</p>;

  return (
    <div className="mx-auto max-w-lg">
      <h1 className="font-display text-4xl text-ink">Hồ sơ</h1>
      <p className="mt-2 text-ink-muted">Cập nhật thông tin cá nhân.</p>

      <form onSubmit={onSubmit} className="mt-8 space-y-4">
        <label className="block text-sm">
          <span className="text-ink-muted">Họ tên</span>
          <input
            type="text"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            required
            className="mt-1 block w-full rounded-sm border border-line bg-surface px-3 py-2 outline-none focus:border-moss"
          />
        </label>

        <label className="block text-sm">
          <span className="text-ink-muted">Số điện thoại</span>
          <input
            type="tel"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            className="mt-1 block w-full rounded-sm border border-line bg-surface px-3 py-2 outline-none focus:border-moss"
          />
        </label>

        <label className="block text-sm">
          <span className="text-ink-muted">Email</span>
          <input
            type="email"
            value={user.email ?? ""}
            disabled
            className="mt-1 block w-full rounded-sm border border-line bg-ink/5 px-3 py-2 text-ink-muted"
          />
          <span className="text-xs text-ink-muted">Email không thể đổi trong MVP.</span>
        </label>

        {error && <p className="text-sm text-danger">{error}</p>}
        {success && <p className="text-sm text-forest">{success}</p>}

        <div className="flex items-center gap-3 pt-2">
          <button
            type="submit"
            disabled={saving}
            className="rounded-full bg-forest px-5 py-2 text-sm font-medium text-white hover:bg-forest-deep disabled:opacity-60"
          >
            {saving ? "Đang lưu…" : "Lưu thay đổi"}
          </button>
          <Link
            href="/account"
            className="text-sm text-forest hover:underline"
          >
            Quay lại tài khoản
          </Link>
        </div>
      </form>
    </div>
  );
}
