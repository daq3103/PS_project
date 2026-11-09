"use client";

import { useEffect, useState, type FormEvent } from "react";
import { api, type StaffRoleChangeDto, type StaffUserDto } from "@/lib/api-client";

const OPTIONS = [
  { key: "platform_manage", label: "Quản lý nền tảng (không cấp quyền)", detail: "Đầy đủ chức năng Shop, trạm cứu hộ và theo dõi hệ thống; không quản lý nhân viên hoặc cấp quyền." },
  { key: "warehouse", label: "Kho & giao hàng", detail: "Xem đơn, đóng gói, tạo vận đơn, quản lý lô hàng, điều chỉnh tồn kho và xem báo cáo bán hàng." },
  { key: "customer_support", label: "Chăm sóc khách hàng Shop", detail: "Xem đơn và xử lý đánh giá, yêu cầu hỗ trợ của khách mua hàng." },
  { key: "rescue_manage", label: "Quản lý trạm cứu hộ", detail: "Hồ sơ bé, tiếp nhận, phân công, nơi chăm sóc, kiểm duyệt tin và bàn giao nhận nuôi." },
  { key: "rescue_care", label: "Chăm sóc cứu hộ", detail: "Chỉ xem và cập nhật các bé, tin báo hoặc công việc được giao." },
  { key: "rescue_finance", label: "Tài chính cứu hộ", detail: "Sổ thu chi, đối soát và đề nghị chi riêng của trạm; không tự đọc hồ sơ chăm sóc." },
] as const;

function permissionLabel(permissions: string[]) {
  if (!permissions.length) return "Khách hàng";
  return OPTIONS.filter(option => permissions.includes(option.key)).map(option => option.label).join(" + ");
}

export default function AdminStaffPage() {
  const [allowed, setAllowed] = useState(false);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [searched, setSearched] = useState("");
  const [users, setUsers] = useState<StaffUserDto[]>([]);
  const [changes, setChanges] = useState<StaffRoleChangeDto[]>([]);
  const [selected, setSelected] = useState<StaffUserDto | null>(null);
  const [draft, setDraft] = useState<string[]>([]);
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    let active = true;
    void api.me().then(async ({ user }) => {
      if (!active) return;
      if (user?.role !== "owner") return;
      setAllowed(true);
      const [people, history] = await Promise.all([api.adminStaffUsers(), api.adminStaffChanges()]);
      if (active) { setUsers(people); setChanges(history); }
    }).catch((cause) => { if (active) setError(cause instanceof Error ? cause.message : "Không tải được danh sách nhân viên."); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  async function search(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const term = query.trim();
    if (term.length === 1) { setError("Nhập ít nhất 2 ký tự để tìm tài khoản."); return; }
    setError(""); setMessage(""); setSearched(term); setSelected(null);
    try { setUsers(await api.adminStaffUsers(term)); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Không tìm được tài khoản."); }
  }

  function choose(person: StaffUserDto) {
    setSelected(person);
    setDraft([...person.staff_permissions]);
    setConfirming(false); setError(""); setMessage("");
  }

  function toggle(permission: string) {
    setDraft(current => current.includes(permission) ? current.filter(item => item !== permission) : [...current, permission]);
    setConfirming(false);
  }

  async function save() {
    if (!selected) return;
    setBusy(true); setError(""); setMessage("");
    try {
      const updated = await api.adminSetStaffPermissions(selected.id, draft);
      setUsers(current => current.map(person => person.id === updated.id ? updated : person));
      setSelected(updated); setDraft(updated.staff_permissions); setConfirming(false);
      setChanges(await api.adminStaffChanges());
      setMessage(`Đã cập nhật quyền của ${updated.full_name}. Người này cần đăng nhập lại để sử dụng quyền mới.`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể cập nhật quyền.");
    } finally { setBusy(false); }
  }

  if (loading) return <p className="text-ink-muted">Đang tải quyền nhân viên…</p>;
  if (!allowed) return <p role="alert" className="text-danger">Chỉ quản trị viên được quản lý quyền nhân viên.</p>;

  const changed = selected && [...draft].sort().join(",") !== [...selected.staff_permissions].sort().join(",");

  return <div className="mx-auto max-w-6xl space-y-6">
    <header>
      <h1 className="font-display text-3xl text-forest">Nhân viên & quyền</h1>
      <p className="mt-2 max-w-3xl text-sm text-ink-muted">Chọn tài khoản đã đăng ký và cấp các nhóm quyền phù hợp. Quyền Shop và Trạm cứu hộ được cấp riêng; người này cần đăng nhập lại sau khi đổi quyền.</p>
    </header>

    <div className="grid gap-3 md:grid-cols-2">{OPTIONS.map(option => <div key={option.key} className="rounded-xl border border-line bg-surface p-4">
      <h2 className="font-semibold text-forest">{option.label}</h2><p className="mt-1 text-sm text-ink-muted">{option.detail}</p>
    </div>)}</div>
    <p className="text-sm text-ink-muted">Quản trị viên có toàn bộ quyền và có thể quản lý sản phẩm, khuyến mãi, thống kê, nhân viên. Quyền quản trị viên không thể cấp tại trang này.</p>

    {error && <p role="alert" className="rounded-lg border border-danger/30 bg-danger/5 p-3 text-sm text-danger">{error}</p>}
    {message && <p role="status" className="rounded-lg border border-forest/30 bg-forest/5 p-3 text-sm text-forest">{message}</p>}

    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(300px,0.85fr)]">
      <section className="min-w-0 rounded-xl border border-line bg-surface p-4 sm:p-5">
        <h2 className="font-display text-xl text-forest">Tìm tài khoản</h2>
        <form onSubmit={search} className="mt-4 flex flex-col gap-2 sm:flex-row">
          <label htmlFor="staff-search" className="sr-only">Tên tài khoản, họ tên, email hoặc số điện thoại</label>
          <input id="staff-search" value={query} onChange={event => setQuery(event.target.value)} placeholder="Tên tài khoản, họ tên, email hoặc số điện thoại" className="min-w-0 flex-1 rounded-lg border border-line bg-paper px-3 py-2 text-sm" />
          <button type="submit" className="rounded-full bg-forest px-5 py-2 text-sm font-medium text-white">Tìm kiếm</button>
        </form>
        <p className="mt-2 text-xs text-ink-muted">{searched ? `Kết quả cho “${searched}”` : "Đang hiển thị nhân viên hiện có. Tìm theo tên tài khoản, họ tên, email hoặc số điện thoại để thêm người mới."}</p>
        <div className="mt-4 space-y-2">{users.length ? users.map(person => <button key={person.id} type="button" onClick={() => choose(person)} aria-pressed={selected?.id === person.id} className={`w-full rounded-lg border p-3 text-left transition ${selected?.id === person.id ? "border-forest bg-forest/5" : "border-line hover:border-forest"}`}>
          <span className="block font-medium">{person.full_name}{!person.is_active && <span className="ml-2 text-xs text-danger">Đã khóa</span>}</span>
          {person.username && <span className="mt-0.5 block break-all text-sm">@{person.username}</span>}
          <span className="mt-0.5 block break-all text-xs text-ink-muted">{person.email ?? person.phone ?? "Chưa có thông tin liên hệ"}</span>
          <span className="mt-1 block text-xs text-forest">{person.role === "owner" ? "Quản trị viên" : permissionLabel(person.staff_permissions)}</span>
        </button>) : <p className="rounded-lg bg-paper p-4 text-sm text-ink-muted">{searched ? "Không tìm thấy tài khoản phù hợp." : "Chưa có nhân viên. Tìm một tài khoản khách hàng để cấp quyền."}</p>}</div>
      </section>

      <section className="h-fit rounded-xl border border-line bg-surface p-4 sm:p-5">
        <h2 className="font-display text-xl text-forest">Cấp quyền</h2>
        {!selected ? <p className="mt-3 text-sm text-ink-muted">Chọn một tài khoản ở danh sách bên trái.</p> : <>
          <p className="mt-3 font-medium">{selected.full_name}</p>
          {selected.username && <p className="break-all text-sm">@{selected.username}</p>}
          <p className="break-all text-sm text-ink-muted">{selected.email ?? selected.phone}</p>
          {selected.role === "owner" ? <p className="mt-4 text-sm text-ink-muted">Không thể thay đổi tài khoản quản trị viên tại đây.</p> : <>
            <div className="mt-5 space-y-3">{OPTIONS.map(option => <label key={option.key} className="flex cursor-pointer gap-3 rounded-lg border border-line p-3">
              <input type="checkbox" checked={draft.includes(option.key)} onChange={() => toggle(option.key)} disabled={!selected.is_active && !selected.staff_permissions.includes(option.key)} className="mt-1 accent-forest" />
              <span><span className="block text-sm font-medium">{option.label}</span><span className="mt-0.5 block text-xs text-ink-muted">{option.detail}</span></span>
            </label>)}</div>
            <p className="mt-4 text-sm">Quyền sau khi lưu: <strong className="text-forest">{permissionLabel(draft)}</strong></p>
            {changed && !confirming && <button type="button" onClick={() => setConfirming(true)} className="mt-4 rounded-full bg-forest px-5 py-2 text-sm font-medium text-white">Tiếp tục</button>}
            {changed && confirming && <div className="mt-4 rounded-lg border border-honey/40 bg-honey/5 p-4 text-sm"><p>Xác nhận đổi quyền cho <strong>{selected.full_name}</strong>? Các phiên đăng nhập hiện tại của người này sẽ kết thúc.</p><div className="mt-3 flex flex-wrap gap-2"><button type="button" disabled={busy} onClick={() => void save()} className="rounded-full bg-forest px-4 py-2 font-medium text-white disabled:opacity-50">{busy ? "Đang lưu…" : "Xác nhận cấp quyền"}</button><button type="button" onClick={() => setConfirming(false)} className="rounded-full border border-line px-4 py-2">Hủy</button></div></div>}
          </>}
        </>}
      </section>
    </div>

    <section className="rounded-xl border border-line bg-surface p-4 sm:p-5"><h2 className="font-display text-xl text-forest">Thay đổi gần đây</h2>
      {changes.length ? <ul className="mt-4 divide-y divide-line">{changes.map((change, index) => <li key={`${change.target_user_id}-${change.created_at}-${index}`} className="py-3 text-sm"><strong>{change.target_name}</strong>: {permissionLabel(change.old_permissions)} → {permissionLabel(change.new_permissions)}<span className="mt-1 block text-xs text-ink-muted">{change.actor_name} · {new Date(change.created_at).toLocaleString("vi-VN")}</span></li>)}</ul> : <p className="mt-3 text-sm text-ink-muted">Chưa có thay đổi quyền.</p>}
    </section>
  </div>;
}
