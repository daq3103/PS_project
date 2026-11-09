"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { api, type CommunityPostAdminOut, type CommunityAuditOut, type PetOptions } from "@/lib/api-client";
import { PetDetailsView } from "@/components/community/PetDetailsView";
import { PhotoGallery } from "@/components/community/PhotoGallery";
import { CommunityAdminNav } from "@/components/community/AdminNav";
import { DataTable, type Column } from "@/components/admin/DataTable";
import { Drawer } from "@/components/admin/Drawer";
import { FilterBar, FilterField } from "@/components/admin/FilterBar";
import { useConfirm } from "@/components/admin/ConfirmDialog";
import { auditActionLabels, auditStatusLabels } from "@/components/community/labels";

const MOD_LABELS: Record<string, string> = {
  pending: "Chờ duyệt",
  approved: "Đã duyệt",
  rejected: "Từ chối",
  hidden: "Đã gỡ",
};

const LIFE_LABELS: Record<string, string> = {
  open: "Mở",
  resolved: "Giải quyết",
  closed: "Đóng",
  expired: "Hết hạn",
};

const TYPE_LABELS: Record<string, string> = {
  lost_pet: "Mất",
  found_pet: "Nhặt được",
  adoption: "Nhận nuôi",
};

export default function AdminCommunityPage() {
  const [posts, setPosts] = useState<CommunityPostAdminOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [filters, setFilters] = useState({
    q: "",
    post_type: "",
    moderation_status: "",
    lifecycle_status: "",
  });
  const [selected, setSelected] = useState<CommunityPostAdminOut | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [history, setHistory] = useState<CommunityAuditOut[]>([]);
  const [petOptions, setPetOptions] = useState<PetOptions | null>(null);
  const [offset, setOffset] = useState(0);
  const [busy, setBusy] = useState(false);
  const { confirm, dialog } = useConfirm();
  const requestId = useRef(0);

  const load = useCallback(async () => {
    const currentRequest = ++requestId.current;
    setLoading(true);
    setError("");
    try {
      const data = await api.adminListCommunityPosts({
        q: filters.q || undefined,
        post_type: (filters.post_type as "lost_pet" | "found_pet" | "adoption") || undefined,
        moderation_status:
          (filters.moderation_status as "pending" | "approved" | "rejected" | "hidden") || undefined,
        lifecycle_status: (filters.lifecycle_status as "open" | "resolved" | "closed" | "expired") || undefined,
        limit: 50,
        offset,
      });
      if (currentRequest === requestId.current) setPosts(data);
    } catch (e) {
      if (currentRequest === requestId.current) setError(e instanceof Error ? e.message : "Không tải được");
    } finally {
      if (currentRequest === requestId.current) setLoading(false);
    }
  }, [filters, offset]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 300);
    return () => { window.clearTimeout(timer); ++requestId.current; };
  }, [load]);

  useEffect(() => { void api.communityPetOptions().then(setPetOptions).catch(() => setPetOptions(null)); }, []);

  useEffect(() => {
    setHistory([]);
    if (selected) void api.adminCommunityAudit(selected.id).then(setHistory).catch(() => setHistory([]));
  }, [selected]);

  async function moderate(id: string, action: "approve" | "reject" | "hide") {
    if (busy) return;
    const reason = action === "approve" ? undefined : window.prompt("Nhập lý do từ chối / gỡ tin:")?.trim();
    if (action !== "approve" && !reason) return;
    const ok = await confirm({
      title: action === "approve" ? "Duyệt tin" : action === "reject" ? "Từ chối tin" : "Gỡ tin",
      message: "Bạn chắc chắn muốn thực hiện?",
      variant: action === "approve" ? "primary" : "danger",
      confirmText: "Xác nhận",
    });
    if (!ok) return;
    setBusy(true);
    try {
      const updated = await api.adminModerateCommunityPost(id, { action, reason, version: posts.find(p => p.id === id)?.version });
      ++requestId.current;
      setPosts(old => old.flatMap(post => post.id !== id ? [post] : filters.moderation_status && filters.moderation_status !== updated.moderation_status ? [] : [updated]));
      await load();
      if (selected?.id === id) setSelected(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Thao tác thất bại");
    } finally {
      setBusy(false);
    }
  }

  const columns: Column<CommunityPostAdminOut>[] = [
    {
      key: "type",
      header: "Loại",
      cell: (row) => TYPE_LABELS[row.post_type],
    },
    {
      key: "title",
      header: "Tiêu đề",
      cell: (row) => (
        <button
          type="button"
          onClick={() => {
            setSelected(row);
            setDrawerOpen(true);
          }}
          className="text-left text-forest hover:underline"
        >
          {row.title}
        </button>
      ),
    },
    { key: "author", header: "Người đăng", cell: (row) => row.author_name },
    {
      key: "mod",
      header: "Kiểm duyệt",
      cell: (row) => MOD_LABELS[row.moderation_status],
    },
    {
      key: "life",
      header: "Vòng đời",
      cell: (row) => LIFE_LABELS[row.lifecycle_status],
    },
    {
      key: "actions",
      header: "",
      align: "right",
      cell: (row) => (
        <div className="flex justify-end gap-2">
          {row.moderation_status === "pending" && (
            <>
              <button
                type="button"
                onClick={() => void moderate(row.id, "approve")}
                className="rounded-full bg-forest px-3 py-1 text-xs text-white hover:bg-forest-deep"
              >
                Duyệt
              </button>
              <button
                type="button"
                onClick={() => void moderate(row.id, "reject")}
                className="rounded-full border border-line px-3 py-1 text-xs text-ink hover:bg-forest/8"
              >
                Từ chối
              </button>
            </>
          )}
          {row.moderation_status === "approved" && (
            <button
              type="button"
              onClick={() => void moderate(row.id, "hide")}
              className="rounded-full border border-line px-3 py-1 text-xs text-ink hover:bg-forest/8"
            >
              Gỡ
            </button>
          )}
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-4">
      <CommunityAdminNav />
      <div className="flex items-center justify-between">
        <h1 className="font-display text-2xl text-forest">Trạm cứu hộ</h1>
      </div>

      {error && <p className="text-sm text-danger">{error}</p>}

      <FilterBar>
        <FilterField label="Tìm kiếm">
          <input
            value={filters.q}
            onChange={(e) => setFilters((f) => ({ ...f, q: e.target.value }))}
            onKeyDown={(e) => e.key === "Enter" && void load()}
            placeholder="Tiêu đề/mô tả"
            className="rounded-sm border border-line bg-paper px-2 py-1.5 text-sm"
          />
        </FilterField>
        <FilterField label="Loại">
          <select
            value={filters.post_type}
            onChange={(e) => setFilters((f) => ({ ...f, post_type: e.target.value }))}
            className="rounded-sm border border-line bg-paper px-2 py-1.5 text-sm"
          >
            <option value="">Tất cả</option>
            <option value="lost_pet">Tin mất</option>
            <option value="found_pet">Tin nhặt được</option>
            <option value="adoption">Nhận nuôi</option>
          </select>
        </FilterField>
        <FilterField label="Kiểm duyệt">
          <select
            value={filters.moderation_status}
            onChange={(e) => setFilters((f) => ({ ...f, moderation_status: e.target.value }))}
            className="rounded-sm border border-line bg-paper px-2 py-1.5 text-sm"
          >
            <option value="">Tất cả</option>
            <option value="pending">Chờ duyệt</option>
            <option value="approved">Đã duyệt</option>
            <option value="rejected">Từ chối</option>
            <option value="hidden">Đã gỡ</option>
          </select>
        </FilterField>
        <FilterField label="Vòng đời">
          <select
            value={filters.lifecycle_status}
            onChange={(e) => setFilters((f) => ({ ...f, lifecycle_status: e.target.value }))}
            className="rounded-sm border border-line bg-paper px-2 py-1.5 text-sm"
          >
            <option value="">Tất cả</option>
            <option value="open">Mở</option>
            <option value="resolved">Giải quyết</option>
            <option value="closed">Đóng</option>
            <option value="expired">Hết hạn</option>
          </select>
        </FilterField>
        <button
          type="button"
          onClick={() => void load()}
          className="rounded-full bg-forest px-4 py-1.5 text-sm text-white hover:bg-forest-deep"
        >
          Lọc
        </button>
      </FilterBar>

      <DataTable
        columns={columns}
        rows={posts}
        keyExtractor={(row) => row.id}
        onRowClick={(row) => { setSelected(row); setDrawerOpen(true); }}
        rowAriaLabel={(row) => `Mở tin ${row.title}`}
        loading={loading}
        empty={error ? "Chưa tải được tin. Vui lòng thử lại." : "Không có kết quả phù hợp."}
      />
      <div className="flex gap-3"><button disabled={!offset || loading} onClick={() => setOffset(v => Math.max(0, v - 50))} className="rounded-full border px-4 py-2 disabled:opacity-40">Trang trước</button><button disabled={posts.length < 50 || loading} onClick={() => setOffset(v => v + 50)} className="rounded-full border px-4 py-2 disabled:opacity-40">Trang sau</button></div>

      {dialog}

      <Drawer open={drawerOpen} onClose={() => setDrawerOpen(false)} title={selected?.title ?? "Chi tiết"}>
        {selected && (
          <div className="space-y-4 text-sm">
            <PostStatusBadge
              moderationStatus={selected.moderation_status}
              lifecycleStatus={selected.lifecycle_status}
            />
            <p>{selected.description}</p>
            <Link href={`/admin/community/${selected.id}/edit`} className="text-forest underline">Sửa nội dung</Link>
            <PhotoGallery images={selected.images} title={selected.title} />
            {petOptions && <PetDetailsView post={selected} options={petOptions} />}
            {selected.moderation_reason && <p>Lý do kiểm duyệt: {selected.moderation_reason}</p>}
            <div className="grid gap-2 text-ink-muted">
              <p>Loài: {({ dog: "Chó", cat: "Mèo", other: "Khác" })[selected.pet_type]}</p>
              <p>Giống: {selected.breed ?? "—"}</p>
              <p>Màu: {selected.color ?? "—"}</p>
              <p>Địa điểm: {selected.province_name}</p>
            </div>
            <div className="rounded-sm bg-paper p-3">
              <p className="font-medium text-ink">Liên hệ</p>
              <p>SĐT: {selected.contact_phone}</p>
              {selected.contact_zalo && <p>Zalo: {selected.contact_zalo}</p>}
              {selected.contact_facebook && (
                <Link href={selected.contact_facebook} target="_blank" className="text-forest hover:underline">
                  Facebook
                </Link>
              )}
            </div>
            <div className="flex gap-2">
              {selected.post_type === "adoption" && <button type="button" disabled={busy} onClick={async () => {
                const action = selected.lifecycle_status === "open" ? "close" : "renew";
                if (!window.confirm(action === "close" ? "Đóng tin và kết thúc các hồ sơ đang xử lý?" : "Gửi tin để duyệt mở lại?")) return;
                setBusy(true);
                try { await api.adminCommunityLifecycle(selected.id, { action, version: selected.version }); setSelected(null); await load(); }
                catch (e) { setError(e instanceof Error ? e.message : "Không cập nhật được"); } finally { setBusy(false); }
              }} className="rounded-full border px-4 py-2">{selected.lifecycle_status === "open" ? "Đóng tin nhận nuôi" : "Mở lại tin"}</button>}
              {selected.moderation_status === "pending" && (
                <>
                  <button
                    type="button"
                    onClick={() => void moderate(selected.id, "approve")}
                    className="rounded-full bg-forest px-4 py-2 text-white hover:bg-forest-deep"
                  >
                    Duyệt
                  </button>
                  <button
                    type="button"
                    onClick={() => void moderate(selected.id, "reject")}
                    className="rounded-full border border-line px-4 py-2 text-ink hover:bg-forest/8"
                  >
                    Từ chối
                  </button>
                </>
              )}
              {selected.moderation_status === "approved" && (
                <button
                  type="button"
                  onClick={() => void moderate(selected.id, "hide")}
                  className="rounded-full border border-line px-4 py-2 text-ink hover:bg-forest/8"
                >
                  Gỡ
                </button>
              )}
            </div>
            <section className="space-y-2 border-t border-line pt-4"><h3 className="font-medium">Lịch sử xử lý</h3>{history.map(item => <div key={item.id} className="rounded-sm bg-paper p-2 text-xs"><p>{new Date(item.created_at).toLocaleString("vi-VN", { timeZone: "Asia/Ho_Chi_Minh" })} · {auditActionLabels[item.action] ?? "Cập nhật thông tin"}</p>{(item.old_status || item.new_status) && <p>{item.old_status ? auditStatusLabels[item.old_status] ?? "Trạng thái trước" : "Chưa có"} → {item.new_status ? auditStatusLabels[item.new_status] ?? "Đã cập nhật" : "Chưa có"}</p>}{item.reason && <p>{item.reason}</p>}</div>)}</section>
          </div>
        )}
      </Drawer>
    </div>
  );
}

function PostStatusBadge({
  moderationStatus,
  lifecycleStatus,
}: {
  moderationStatus: string;
  lifecycleStatus: string;
}) {
  return (
    <div className="flex flex-wrap gap-2">
      <span className="rounded-full bg-forest/10 px-2.5 py-0.5 text-xs font-medium text-forest">
        {MOD_LABELS[moderationStatus]}
      </span>
      <span className="rounded-full bg-ink/10 px-2.5 py-0.5 text-xs font-medium text-ink">
        {LIFE_LABELS[lifecycleStatus]}
      </span>
    </div>
  );
}
