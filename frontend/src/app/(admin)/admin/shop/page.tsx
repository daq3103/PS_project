"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { api, type DashboardOut, type OrderOut } from "@/lib/api-client";
import { formatVnd } from "@/lib/format";
import { KpiCard } from "@/components/admin/KpiCard";
import { DataTable } from "@/components/admin/DataTable";
import type { Column } from "@/components/admin/DataTable";
import { StatusBadge } from "@/components/admin/StatusBadge";

const recentColumns: Column<OrderOut>[] = [
  { key: "code", header: "Mã đơn", cell: (o) => <span className="font-mono">{o.order_code}</span> },
  {
    key: "customer",
    header: "Khách",
    cell: (o) => (
      <div>
        <p>{o.customer_name}</p>
        <p className="text-xs text-ink-muted">{o.customer_phone}</p>
      </div>
    ),
  },
  { key: "total", header: "Tổng", align: "right", cell: (o) => formatVnd(o.total_amount) },
  { key: "status", header: "Trạng thái", cell: (o) => <StatusBadge status={o.status} /> },
  { key: "payment", header: "Thanh toán", cell: (o) => <StatusBadge status={o.payment_status} /> },
  {
    key: "created",
    header: "Thời gian",
    cell: (o) => new Date(o.created_at).toLocaleString("vi-VN"),
  },
  {
    key: "action",
    header: "",
    cell: (o) => (
      <Link
        href={`/admin/orders?open=${o.id}`}
        className="text-forest hover:underline"
      >
        Mở
      </Link>
    ),
  },
];

export default function AdminDashboardPage() {
  const [data, setData] = useState<DashboardOut | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setData(await api.adminDashboard());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Không tải được tổng quan Shop");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl text-forest">Tổng quan Shop</h1>
          <p className="mt-1 text-sm text-ink-muted">
            Theo dõi đơn hàng, doanh thu và tình trạng kho.
          </p>
        </div>
        <button
          type="button"
          onClick={() => void load()}
          disabled={loading}
          className="rounded-full border border-forest px-4 py-1.5 text-sm text-forest hover:bg-forest/8 disabled:opacity-50"
        >
          {loading ? "Đang tải…" : "Làm mới"}
        </button>
      </div>

      {error && <p className="mt-4 text-sm text-danger">{error}</p>}

      {!data && loading && (
        <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="h-24 animate-pulse rounded-sm border border-line bg-surface" />
          ))}
        </div>
      )}

      {data && (
        <>
          <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <KpiCard label="Đơn hôm nay" value={data.orders_today} href="/admin/orders" />
            <KpiCard
              label="Doanh thu hôm nay"
              value={formatVnd(data.revenue_today)}
              tone={data.revenue_today > 0 ? "forest" : "ink"}
            />
            <KpiCard
              label="Đơn chờ xử lý"
              value={data.pending_orders}
              tone={data.pending_orders > 0 ? "honey" : "forest"}
              href="/admin/orders?status=pending"
            />
            <KpiCard
              label="Đánh giá chờ duyệt"
              value={data.pending_reviews}
              tone={data.pending_reviews > 0 ? "honey" : "forest"}
              href="/admin/reviews"
            />
            <KpiCard
              label="Hết hàng"
              value={data.out_of_stock_variants}
              tone={data.out_of_stock_variants > 0 ? "danger" : "forest"}
              href="/admin/inventory-lots"
            />
            <KpiCard
              label="Sắp hết hàng"
              value={data.low_stock_variants}
              tone={data.low_stock_variants > 0 ? "honey" : "forest"}
              href="/admin/inventory-lots"
            />
            <KpiCard
              label="Lô hết hạn"
              value={data.lots_expiring_30d}
              tone={data.lots_expiring_30d > 0 ? "danger" : "forest"}
              href="/admin/reports"
            />
            <KpiCard
              label="Chênh lệch kho"
              value={data.drift_count}
              tone={data.drift_count > 0 ? "danger" : "forest"}
              href="/admin/reports"
            />
          </div>

          <div className="mt-8">
            <h2 className="font-display text-xl">Đơn mới nhất</h2>
            <div className="mt-3">
              <DataTable
                columns={recentColumns}
                rows={data.recent_orders}
                keyExtractor={(o) => o.id}
                onRowClick={(o) => { window.location.href = `/admin/orders?open=${o.id}`; }}
                rowAriaLabel={(o) => `Mở đơn ${o.order_code}`}
                empty="Chưa có đơn hàng."
              />
            </div>
          </div>
        </>
      )}
    </div>
  );
}
