"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api-client";

export function AdoptionForm({ postId }: { postId: string }) {
  const [signedIn, setSignedIn] = useState<boolean | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [success, setSuccess] = useState(false);
  const [key, setKey] = useState("");
  useEffect(() => { setKey(crypto.randomUUID()); void api.me().then(r => setSignedIn(!!r.user)).catch(() => setSignedIn(false)); }, []);
  if (signedIn === null) return <p>Đang tải đăng ký nhận nuôi…</p>;
  if (!signedIn) return <Link className="text-forest underline" href="/login?next=/tram-cuu-ho">Đăng nhập để đăng ký nhận nuôi</Link>;
  if (success) return <p role="status">Đã gửi hồ sơ. <Link href="/account/adoption-requests" className="text-forest underline">Theo dõi hồ sơ</Link></p>;
  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault(); if (busy) return; setBusy(true); setMessage("");
    const form = new FormData(e.currentTarget);
    try {
      await api.applyForAdoption(postId, { applicant_name: String(form.get("applicant_name")), applicant_phone: String(form.get("applicant_phone")),
        applicant_address: String(form.get("applicant_address")), living_condition: String(form.get("living_condition")) }, key);
      setSuccess(true);
    } catch (e) { setMessage(e instanceof Error ? e.message : "Không gửi được hồ sơ"); }
    finally { setBusy(false); }
  }
  return <form onSubmit={submit} onChange={() => setKey(crypto.randomUUID())} className="space-y-4 rounded-sm border border-line p-4">
    <h2 className="font-display text-xl text-forest">Đăng ký nhận nuôi</h2>
    <p className="text-sm text-ink-muted">Thông tin này chỉ dành cho bạn và nhân viên xử lý hồ sơ.</p>
    {message && <p role="alert" className="text-danger">{message}</p>}
    <label className="block">Họ tên<input name="applicant_name" required minLength={2} maxLength={150} className="mt-1 w-full rounded-sm border border-line p-2" /></label>
    <label className="block">Điện thoại<input name="applicant_phone" required type="tel" pattern="\+?[0-9]{9,15}" className="mt-1 w-full rounded-sm border border-line p-2" /></label>
    <label className="block">Địa chỉ<input name="applicant_address" required minLength={5} maxLength={1000} className="mt-1 w-full rounded-sm border border-line p-2" /></label>
    <label className="block">Điều kiện sống và kinh nghiệm chăm sóc<textarea name="living_condition" required minLength={10} maxLength={2000} rows={4} className="mt-1 w-full rounded-sm border border-line p-2" /></label>
    <button disabled={busy} className="rounded-full bg-forest px-5 py-2 text-white disabled:opacity-50">{busy ? "Đang gửi…" : "Gửi hồ sơ"}</button>
  </form>;
}
