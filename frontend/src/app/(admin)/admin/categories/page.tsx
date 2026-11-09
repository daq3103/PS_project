"use client";
import { DeleteRecordButton } from "@/components/admin/DeleteRecordButton";

import Link from "next/link";
import { useCallback, useEffect, useState, type FormEvent } from "react";
import { CategoryCreateForm } from "@/components/admin/CategoryCreateForm";
import { api, type CategoryDto } from "@/lib/api-client";
import { canManagePlatform } from "@/lib/admin-navigation";

export default function AdminCategoriesPage() {
  const [categories, setCategories] = useState<CategoryDto[]>([]);
  const [loading, setLoading] = useState(true);
  const [allowed, setAllowed] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [editing, setEditing] = useState<CategoryDto | null>(null);
  const [name, setName] = useState("");
  const [sortOrder, setSortOrder] = useState(0);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => { setCategories(await api.adminListCategories()); }, []);
  useEffect(() => {
    let active = true;
    void api.me().then(async ({ user }) => {
      if (!active || !canManagePlatform(user)) return;
      setAllowed(true);
      const rows = await api.adminListCategories();
      if (active) setCategories(rows);
    }).catch(cause => { if (active) setError(cause instanceof Error ? cause.message : "Không tải được danh mục."); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  function edit(category: CategoryDto) {
    setEditing(category); setName(category.name); setSortOrder(category.sort_order);
    setError(""); setMessage("");
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editing) return;
    setSaving(true); setError(""); setMessage("");
    try {
      await api.updateCategory(editing.id, { name: name.trim(), sort_order: sortOrder });
      await load(); setEditing(null); setMessage("Đã cập nhật danh mục.");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Không lưu được danh mục."); }
    finally { setSaving(false); }
  }

  if (loading) return <p className="text-ink-muted">Đang tải danh mục…</p>;
  if (!allowed) return <p role="alert" className="text-danger">Chỉ quản trị viên được thay đổi danh mục sản phẩm.</p>;

  return <div className="mx-auto max-w-5xl space-y-6">
    <header className="flex flex-wrap items-end justify-between gap-3">
      <div><h1 className="font-display text-3xl text-forest">Danh mục sản phẩm</h1>
        <p className="mt-2 text-sm text-ink-muted">Chọn danh mục dùng để phân loại sản phẩm. Muốn sắp xếp toàn bộ thanh menu Shop hoặc thêm liên kết, mở phần Thanh menu Shop.</p></div>
      <Link href="/admin/products" className="rounded-full border border-forest px-4 py-2 text-sm font-medium text-forest">Quay lại sản phẩm</Link>
      <Link href="/admin/shop/menu" className="rounded-full border border-forest px-4 py-2 text-sm font-medium text-forest">Thanh menu Shop</Link>
    </header>
    {error && <p role="alert" className="rounded-lg border border-danger/30 bg-danger/5 p-3 text-sm text-danger">{error}</p>}
    {message && <p role="status" className="rounded-lg border border-forest/30 bg-forest/5 p-3 text-sm text-forest">{message}</p>}
    <section className="rounded-xl border border-line bg-surface p-5"><h2 className="mb-4 font-display text-xl text-forest">Tạo danh mục mới</h2>
      <CategoryCreateForm sortOrder={Math.max(-1, ...categories.map(c => c.sort_order)) + 1} onCreated={async category => { await load(); setMessage(`Đã tạo danh mục “${category.name}”. Bạn có thể chọn danh mục này khi thêm sản phẩm.`); }} />
    </section>
    <section className="rounded-xl border border-line bg-surface p-5"><h2 className="font-display text-xl text-forest">Danh mục hiện có</h2>
      {categories.length ? <ul className="mt-4 divide-y divide-line">{categories.map(category => <li key={category.id} tabIndex={0} role="button" aria-label={`Sửa danh mục ${category.name}`} onClick={event => { if (!(event.target as HTMLElement).closest("button,a,input")) edit(category); }} onKeyDown={event => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); edit(category); } }} className="flex cursor-pointer flex-wrap items-center justify-between gap-3 px-2 py-3 transition hover:bg-forest/10 focus-visible:bg-forest/10 focus-visible:outline-2 focus-visible:outline-forest">
        <div><p className="font-medium">{category.name}</p><p className="mt-0.5 text-xs text-ink-muted">{category.is_active ? "Đang sử dụng" : "Đã tắt"} · {category.show_in_nav && category.is_active ? "Có trên menu Shop" : "Ẩn khỏi menu Shop"} · Thứ tự {category.sort_order}</p></div>
        <div className="flex flex-wrap gap-2"><DeleteRecordButton kind="categories" id={category.id} onDeleted={load} />
        <button type="button" className="rounded-full border border-line px-4 py-2 text-sm text-forest hover:bg-forest/10" onClick={async () => { try { await api.updateCategory(category.id, {is_active: !category.is_active}); await load(); } catch(e) { setError(e instanceof Error ? e.message : "Chưa đổi được hiển thị."); } }}>{category.is_active ? "Tắt danh mục" : "Bật danh mục"}</button>
        <button type="button" className="rounded-full border border-line px-4 py-2 text-sm text-forest hover:bg-forest/10" onClick={async () => { try { await api.updateCategory(category.id, {show_in_nav: !category.show_in_nav}); await load(); } catch(e) { setError(e instanceof Error ? e.message : "Chưa đổi được menu Shop."); } }}>{category.show_in_nav ? "Ẩn khỏi menu" : "Hiện trên menu"}</button>
        <button type="button" onClick={() => edit(category)} className="rounded-full border border-line px-4 py-1.5 text-sm text-forest hover:border-forest">Sửa tên / thứ tự</button></div>
      </li>)}</ul> : <p className="mt-4 text-sm text-ink-muted">Chưa có danh mục nào.</p>}
    </section>
    {editing && <section className="rounded-xl border border-line bg-surface p-5"><h2 className="font-display text-xl text-forest">Sửa danh mục</h2>
      <p className="mt-1 text-sm text-ink-muted">Đường dẫn được giữ nguyên để liên kết cũ tiếp tục hoạt động. Danh mục có số thứ tự nhỏ hơn sẽ đứng trước.</p>
      <form onSubmit={save} className="mt-4 flex flex-wrap items-end gap-3">
        <label className="min-w-[220px] flex-1 text-sm">Tên danh mục<input value={name} onChange={event => setName(event.target.value)} required maxLength={150} className="mt-1 block w-full rounded-sm border border-line bg-paper px-3 py-2" /></label>
        <label className="w-32 text-sm">Thứ tự<input type="number" min={0} value={sortOrder} onChange={event => setSortOrder(Math.max(0, Number(event.target.value)))} className="mt-1 block w-full rounded-sm border border-line bg-paper px-3 py-2" /></label>
        <button type="submit" disabled={saving} className="rounded-full bg-forest px-5 py-2 text-sm font-medium text-white disabled:opacity-50">{saving ? "Đang lưu…" : "Lưu thay đổi"}</button>
        <button type="button" onClick={() => setEditing(null)} className="rounded-full border border-line px-5 py-2 text-sm">Hủy</button>
      </form>
    </section>}
  </div>;
}
