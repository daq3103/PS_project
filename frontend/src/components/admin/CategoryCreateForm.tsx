"use client";

import { useState, type FormEvent } from "react";
import { api, type CategoryDto } from "@/lib/api-client";
import { slugify } from "@/lib/slugify";

export function CategoryCreateForm({ onCreated, sortOrder }: { onCreated: (category: CategoryDto) => void | Promise<void>; sortOrder?: number }) {
  const [name, setName] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = name.trim();
    const slug = slugify(trimmed);
    if (!slug) { setError("Nhập tên danh mục có chữ hoặc số."); return; }
    setSaving(true); setError("");
    try {
      const created = await api.createCategory({ name: trimmed, slug, is_active: false, ...(sortOrder === undefined ? {} : { sort_order: sortOrder }) });
      setName("");
      await onCreated(created);
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : "Không tạo được danh mục.";
      setError(message);
    } finally { setSaving(false); }
  }

  return <form onSubmit={submit} className="space-y-3">
    <p className="text-xs text-ink-muted">Danh mục mới được lưu ẩn. Bật hiển thị sau khi đã có sản phẩm.</p>
    <label className="block text-sm"><span className="font-medium">Tên danh mục</span>
      <input value={name} onChange={event => setName(event.target.value)} required maxLength={150} placeholder="Ví dụ: Đồ chơi, Thức ăn, Phụ kiện" className="mt-1 block w-full rounded-sm border border-line bg-paper px-3 py-2 outline-none focus:border-moss" />
    </label>
    {error && <p role="alert" className="text-sm text-danger">{error}</p>}
    <button type="submit" disabled={saving || !name.trim()} className="rounded-full bg-forest px-5 py-2 text-sm font-medium text-white disabled:opacity-50">{saving ? "Đang tạo…" : "Tạo danh mục"}</button>
  </form>;
}
