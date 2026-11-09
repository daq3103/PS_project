"use client";

import { useEffect, useState, type FormEvent } from "react";
import { api, type ShopNavItem } from "@/lib/api-client";
import { canManagePlatform } from "@/lib/admin-navigation";

export default function ShopMenuPage() {
  const [items, setItems] = useState<ShopNavItem[]>([]);
  const [allowed, setAllowed] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [label, setLabel] = useState("");
  const [href, setHref] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    let active = true;
    void api.me().then(async ({user}) => {
      if (!active || !canManagePlatform(user)) return;
      setAllowed(true);
      const rows = await api.adminShopNavigation();
      if (active) setItems(rows);
    }).catch(e => { if (active) setError(e instanceof Error ? e.message : "Không tải được thanh menu."); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  function move(index: number, direction: -1 | 1) {
    const next = [...items];
    const other = index + direction;
    if (other < 0 || other >= next.length) return;
    [next[index], next[other]] = [next[other], next[index]];
    setItems(next); setNotice("");
  }

  function add(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError("");
    const path = href.trim();
    if (!path.startsWith("/") || path.startsWith("//") || path.includes("\\")) {
      setError("Đường dẫn phải là trang nội bộ, bắt đầu bằng /."); return;
    }
    setItems(old => [...old, {key: `custom:${crypto.randomUUID()}`, label: label.trim(), href: path, visible: true}]);
    setLabel(""); setHref(""); setNotice("");
  }

  async function save() {
    setSaving(true); setError(""); setNotice("");
    try {
      setItems(await api.saveShopNavigation(items));
      window.dispatchEvent(new Event("pethome:navigation"));
      setNotice("Đã lưu thanh menu Shop. Khách mở trang mới sẽ thấy thứ tự này.");
    } catch (e) { setError(e instanceof Error ? e.message : "Không lưu được thanh menu."); }
    finally { setSaving(false); }
  }

  if (loading) return <p>Đang tải thanh menu…</p>;
  if (!allowed) return <p role="alert" className="text-danger">Bạn cần quyền quản lý nền tảng để sửa thanh menu Shop.</p>;
  return <div className="mx-auto max-w-4xl space-y-6">
    <header><h1 className="font-display text-3xl text-forest">Thanh menu Shop</h1><p className="mt-2 text-sm text-ink-muted">Đổi vị trí bằng nút lên/xuống, chọn mục cần hiện và thêm đường dẫn đến trang trong PetHome. Mục danh mục lấy tên và đường dẫn từ danh mục sản phẩm.</p></header>
    {error && <p role="alert" className="rounded-xl bg-danger/10 p-3 text-sm text-danger">{error}</p>}
    {notice && <p role="status" className="rounded-xl bg-forest/10 p-3 text-sm text-forest">{notice}</p>}
    <section className="rounded-2xl border border-line bg-surface p-4"><h2 className="font-semibold text-forest">Các mục trên thanh</h2><ol className="mt-3 space-y-2">{items.map((item, index) => <li key={item.key} className="flex flex-wrap items-center gap-3 rounded-xl border border-line p-3">
      <span className="w-6 text-sm text-ink-muted">{index + 1}</span>
      <div className="min-w-0 flex-1"><p className="font-medium">{item.label}</p><p className="break-all text-xs text-ink-muted">{item.href}</p></div>
      <label className="flex cursor-pointer items-center gap-2 text-sm"><input type="checkbox" checked={item.visible} onChange={event => setItems(old => old.map(row => row.key === item.key ? {...row, visible: event.target.checked} : row))} />Hiện</label>
      <div className="flex gap-1"><button type="button" aria-label={`Đưa ${item.label} lên`} disabled={index === 0} onClick={() => move(index, -1)} className="rounded-full border border-line px-3 py-2 text-sm disabled:opacity-30">↑</button><button type="button" aria-label={`Đưa ${item.label} xuống`} disabled={index === items.length - 1} onClick={() => move(index, 1)} className="rounded-full border border-line px-3 py-2 text-sm disabled:opacity-30">↓</button></div>
      {item.key.startsWith("custom:") && <button type="button" onClick={() => setItems(old => old.filter(row => row.key !== item.key))} className="rounded-full px-3 py-2 text-sm text-danger">Xóa</button>}
    </li>)}</ol></section>
    <form onSubmit={add} className="space-y-3 rounded-2xl border border-line bg-surface p-4"><h2 className="font-semibold text-forest">Thêm mục liên kết</h2><div className="grid gap-3 sm:grid-cols-2"><label className="text-sm">Tên hiển thị<input value={label} onChange={e => setLabel(e.target.value)} required maxLength={60} className="mt-1 w-full rounded-xl border border-line p-3" /></label><label className="text-sm">Đường dẫn nội bộ<input value={href} onChange={e => setHref(e.target.value)} required maxLength={300} placeholder="/tram-cuu-ho" className="mt-1 w-full rounded-xl border border-line p-3" /></label></div><button type="submit" className="rounded-full border border-forest px-4 py-2 text-sm text-forest">+ Thêm vào danh sách</button></form>
    <button type="button" disabled={saving} onClick={() => void save()} className="rounded-full bg-forest px-6 py-3 text-sm font-semibold text-white disabled:opacity-50">{saving ? "Đang lưu…" : "Lưu thanh menu"}</button>
  </div>;
}
