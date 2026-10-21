"use client";

import { useCallback, useEffect, useState } from "react";
import { api, type DriftReportOut, type StockMovementOut } from "@/lib/api-client";
import { DataTable, type Column } from "@/components/admin/DataTable";
import { StatusBadge } from "@/components/admin/StatusBadge";
import { FilterBar, FilterField } from "@/components/admin/FilterBar";

const REASON_LABELS: Record<string, string> = {
  lot_import: "Nhập lô",
  stocktake_adjust: "Kiểm kê",
  damaged_adjust: "Hư hỏng",
  manual_correct: "Sửa tay",
};

export default function AdminReportsPage() {
  const [report, setReport] = useState<DriftReportOut | null>(null);
  const [movements, setMovements] = useState<StockMovementOut[]>([]);
  const [reason, setReason] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [loading, setLoading] = useState(true);
  const [moveLoading, setMoveLoading] = useState(false);
  const [error, setError] = useState("");

  const loadDrift = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setReport(await api.adminDriftReport());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Không tải được báo cáo");
    } finally {
      setLoading(false);
    }
  }, []);

  const loadMovements = useCallback(async () => {
    setMoveLoading(true);
    try {
      const data = await api.adminListStockMovements({
        reason: reason || undefined,
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
        limit: 100,
      });
      setMovements(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Không tải được sổ kho");
    } finally {
      setMoveLoading(false);
    }
  }, [reason, dateFrom, dateTo]);

  useEffect(() => {
    void loadDrift();
  }, [loadDrift]);

  useEffect(() => {
    void loadMovements();
  }, [loadMovements]);

  const driftColumns: Column<DriftReportOut["lots"][number]>[] = [
    { key: "lot", header: "Lô", cell: (l) => <span className="font-medium">{l.lot_no}</span> },
    {
      key: "variant",
      header: "Variant",
      cell: (l) => <span className="font-mono text-xs">{l.variant_id.slice(0, 8)}…</span>,
    },
    { key: "on_hand", header: "Tồn", align: "right", cell: (l) => l.qty_on_hand },
    { key: "movements", header: "Σ movements", align: "right", cell: (l) => l.movements_sum },
    {
      key: "drift",
      header: "Drift",
      align: "right",
      cell: (l) => (
        <span className={l.drift !== 0 ? "font-semibold text-honey" : ""}>{l.drift}</span>
      ),
    },
  ];

  const movementColumns: Column<StockMovementOut>[] = [
    {
      key: "time",
      header: "Thời gian",
      cell: (m) => new Date(m.created_at).toLocaleString("vi-VN"),
    },
    { key: "lot", header: "Lô", cell: (m) => m.lot_no },
    {
      key: "variant",
      header: "Variant",
      cell: (m) => <span className="font-mono text-xs">{m.variant_id.slice(0, 8)}…</span>,
    },
    {
      key: "qty",
      header: "SL",
      align: "right",
      cell: (m) => (
        <span className={m.qty_delta > 0 ? "text-forest" : "text-danger"}>
          {m.qty_delta > 0 ? `+${m.qty_delta}` : m.qty_delta}
        </span>
      ),
    },
    {
      key: "reason",
      header: "Lý do",
      cell: (m) => REASON_LABELS[m.reason] ?? m.reason,
    },
    { key: "note", header: "Ghi chú", cell: (m) => m.note ?? "—" },
  ];

  return (
    <div className="space-y-8">
      <div>
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="font-display text-3xl text-forest">Drift kho</h1>
            <p className="mt-1 text-sm text-ink-muted">
              Đối chiếu tồn lô với tổng <code className="text-xs">stock_movements</code>.
            </p>
          </div>
          <button
            type="button"
            onClick={() => {
              void loadDrift();
              void loadMovements();
            }}
            className="rounded-full border border-forest px-4 py-1.5 text-sm text-forest hover:bg-forest/8"
          >
            Chạy lại
          </button>
        </div>

        {error && <p className="mt-4 text-sm text-danger">{error}</p>}
        {loading && !report && <p className="mt-6 text-ink-muted">Đang kiểm tra…</p>}

        {report && !loading && (
          <div className="mt-4">
            <p className="mb-2 text-sm text-ink-muted">
              {report.lot_count} lô ·{" "}
              <span className={report.drift_count > 0 ? "font-semibold text-honey" : "text-forest"}>
                {report.drift_count} lệch
              </span>
            </p>
            <DataTable
              columns={driftColumns}
              rows={report.lots}
              keyExtractor={(l) => l.lot_id}
              empty="Không có dữ liệu drift."
            />
          </div>
        )}
      </div>

      <div>
        <h2 className="font-display text-2xl text-forest">Sổ kho</h2>
        <FilterBar>
          <FilterField label="Lý do">
            <select
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              className="rounded-sm border border-line bg-paper px-2 py-1.5"
            >
              <option value="">Tất cả</option>
              {Object.entries(REASON_LABELS).map(([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ))}
            </select>
          </FilterField>
          <FilterField label="Từ ngày">
            <input
              type="date"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
              className="rounded-sm border border-line bg-paper px-2 py-1.5"
            />
          </FilterField>
          <FilterField label="Đến ngày">
            <input
              type="date"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
              className="rounded-sm border border-line bg-paper px-2 py-1.5"
            />
          </FilterField>
        </FilterBar>
        <div className="mt-4">
          <DataTable
            columns={movementColumns}
            rows={movements}
            keyExtractor={(m) => m.id}
            loading={moveLoading}
            empty="Không có bút toán kho."
          />
        </div>
      </div>
    </div>
  );
}
