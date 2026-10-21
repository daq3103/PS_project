"use client";

import { useCallback, useEffect, useState } from "react";
import { api, type ReviewOut } from "@/lib/api-client";
import { DataTable, type Column } from "@/components/admin/DataTable";
import { StatusBadge } from "@/components/admin/StatusBadge";
import { useConfirm } from "@/components/admin/ConfirmDialog";

export default function AdminReviewsPage() {
  const [reviews, setReviews] = useState<ReviewOut[]>([]);
  const [pendingOnly, setPendingOnly] = useState(true);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const { confirm, dialog } = useConfirm();

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setReviews(await api.adminListReviews({ pending_only: pendingOnly }));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Không tải được đánh giá");
    } finally {
      setLoading(false);
    }
  }, [pendingOnly]);

  useEffect(() => {
    void load();
  }, [load]);

  async function decide(id: string, approve: boolean) {
    if (!approve) {
      const ok = await confirm({
        title: "Từ chối đánh giá",
        message: "Từ chối sẽ xoá đánh giá này. Tiếp tục?",
        variant: "danger",
        confirmText: "Xoá",
      });
      if (!ok) return;
    }
    try {
      await api.adminApproveReview(id, approve);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Thao tác thất bại");
    }
  }

  const columns: Column<ReviewOut>[] = [
    {
      key: "product",
      header: "Sản phẩm",
      cell: (r) => (
        <div>
          <p className="font-medium">{r.product_name ?? r.product_id.slice(0, 8)}</p>
          <p className="text-xs text-ink-muted">{r.product_id.slice(0, 8)}…</p>
        </div>
      ),
    },
    {
      key: "reviewer",
      header: "Người đánh giá",
      cell: (r) => r.reviewer_name,
    },
    {
      key: "rating",
      header: "Sao",
      cell: (r) => <span className="font-medium text-honey">{r.rating}/5</span>,
    },
    {
      key: "content",
      header: "Nội dung",
      cell: (r) => <p className="max-w-md truncate">{r.content ?? "—"}</p>,
    },
    {
      key: "created",
      header: "Thời gian",
      cell: (r) => new Date(r.created_at).toLocaleString("vi-VN"),
    },
    {
      key: "status",
      header: "Trạng thái",
      cell: (r) => (
        <StatusBadge status={r.is_approved ? "delivered" : "pending"} />
      ),
    },
    {
      key: "actions",
      header: "",
      cell: (r) =>
        !r.is_approved ? (
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => void decide(r.id, true)}
              className="rounded-full bg-forest px-3 py-1 text-xs text-white hover:bg-forest-deep"
            >
              Duyệt
            </button>
            <button
              type="button"
              onClick={() => void decide(r.id, false)}
              className="rounded-full border border-danger px-3 py-1 text-xs text-danger hover:bg-danger/5"
            >
              Từ chối
            </button>
          </div>
        ) : (
          <span className="text-xs text-ink-muted">Đã duyệt</span>
        ),
    },
  ];

  return (
    <div>
      {dialog}
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl text-forest">Duyệt đánh giá</h1>
          <p className="mt-1 text-sm text-ink-muted">Phê duyệt để hiện trên storefront.</p>
        </div>
        <label className="flex items-center gap-2 text-sm text-ink-muted">
          <input
            type="checkbox"
            checked={pendingOnly}
            onChange={(e) => setPendingOnly(e.target.checked)}
          />
          Chỉ chờ duyệt
        </label>
      </div>

      {error && <p className="mt-4 text-sm text-danger">{error}</p>}

      <div className="mt-4">
        <DataTable
          columns={columns}
          rows={reviews}
          keyExtractor={(r) => r.id}
          loading={loading}
          empty="Không có đánh giá."
        />
      </div>
    </div>
  );
}
