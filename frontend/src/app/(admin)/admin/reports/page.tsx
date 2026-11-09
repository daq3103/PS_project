"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { api, type DriftReportOut, type StockMovementOut, type SalesReport } from "@/lib/api-client";
import { formatVnd } from "@/lib/format";
import { DataTable, type Column } from "@/components/admin/DataTable";
import { StatusBadge } from "@/components/admin/StatusBadge";
import { FilterBar, FilterField } from "@/components/admin/FilterBar";
import { Drawer } from "@/components/admin/Drawer";

const REASON_LABELS: Record<string, string> = {
  lot_import: "Nhập lô",
  stocktake_adjust: "Kiểm kê",
  damaged_adjust: "Hư hỏng",
  manual_correct: "Sửa tay",
};

export default function AdminReportsPage() {
  const [report, setReport] = useState<DriftReportOut | null>(null);
  const [sales, setSales] = useState<SalesReport | null>(null);
  const [salesError, setSalesError] = useState("");
  const [movements, setMovements] = useState<StockMovementOut[]>([]);
  const [reason, setReason] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [loading, setLoading] = useState(true);
  const [moveLoading, setMoveLoading] = useState(false);
  const [error, setError] = useState("");
  const [selectedDrift, setSelectedDrift] = useState<DriftReportOut["lots"][number] | null>(null);
  const [selectedMovement, setSelectedMovement] = useState<StockMovementOut | null>(null);

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

  const loadSales = useCallback(async () => {
    setSalesError("");
    try { setSales(await api.salesReport(dateFrom, dateTo)); }
    catch (e) { setSales(null); setSalesError(e instanceof Error ? e.message : "Chưa tải được số liệu bán hàng."); }
  }, [dateFrom, dateTo]);
  useEffect(() => { void loadSales(); }, [loadSales]);

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
      header: "Mẫu hàng",
      cell: (l) => <span className="font-mono text-xs">{l.variant_id.slice(0, 8)}…</span>,
    },
    { key: "on_hand", header: "Tồn", align: "right", cell: (l) => l.qty_on_hand },
    { key: "movements", header: "Tổng thay đổi", align: "right", cell: (l) => l.movements_sum },
    {
      key: "drift",
      header: "Chênh lệch",
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
      header: "Mẫu hàng",
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
  const movementDay = (row: StockMovementOut) => new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Ho_Chi_Minh", year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date(row.created_at));
  const movementDayColors = new Map<string, number>();
  for (const row of movements) {
    const day = movementDay(row);
    if (!movementDayColors.has(day)) movementDayColors.set(day, movementDayColors.size % 2);
  }
  const reportHref = (metric: string, day?: string, status?: string) => {
    const query = new URLSearchParams({ date_from: day ?? sales?.date_from ?? "", date_to: day ?? sales?.date_to ?? "", report_metric: metric });
    if (status) query.set("status", status);
    return `/admin/orders?${query.toString()}`;
  };

  return (
    <div className="space-y-8">
      {selectedDrift && <Drawer open onClose={() => setSelectedDrift(null)} title={`Đối chiếu lô ${selectedDrift.lot_no}`}><dl className="space-y-3 text-sm"><div><dt className="text-ink-muted">Mã mẫu hàng</dt><dd className="font-mono">{selectedDrift.variant_id}</dd></div><div><dt className="text-ink-muted">Tồn thực tế</dt><dd>{selectedDrift.qty_on_hand}</dd></div><div><dt className="text-ink-muted">Tổng thay đổi trong sổ</dt><dd>{selectedDrift.movements_sum}</dd></div><div><dt className="text-ink-muted">Chênh lệch</dt><dd className={selectedDrift.drift ? "font-semibold text-danger" : "text-forest"}>{selectedDrift.drift}</dd></div></dl><Link href="/admin/inventory-lots" className="mt-5 inline-block text-sm text-forest underline">Mở kho & lô hàng</Link></Drawer>}
      {selectedMovement && <Drawer open onClose={() => setSelectedMovement(null)} title={`Bút toán kho · ${selectedMovement.lot_no}`}><dl className="space-y-3 text-sm"><div><dt className="text-ink-muted">Thời gian</dt><dd>{new Date(selectedMovement.created_at).toLocaleString("vi-VN")}</dd></div><div><dt className="text-ink-muted">Lô / mẫu hàng</dt><dd>{selectedMovement.lot_no} · {selectedMovement.variant_id}</dd></div><div><dt className="text-ink-muted">Số lượng thay đổi</dt><dd>{selectedMovement.qty_delta > 0 ? "+" : ""}{selectedMovement.qty_delta}</dd></div><div><dt className="text-ink-muted">Lý do</dt><dd>{REASON_LABELS[selectedMovement.reason] ?? selectedMovement.reason}</dd></div><div><dt className="text-ink-muted">Nguồn ghi nhận</dt><dd>{selectedMovement.ref_type ?? "—"}{selectedMovement.ref_id ? ` · ${selectedMovement.ref_id}` : ""}</dd></div><div><dt className="text-ink-muted">Ghi chú</dt><dd className="whitespace-pre-wrap">{selectedMovement.note || "—"}</dd></div></dl></Drawer>}
      <section className="space-y-4">
        <h1 className="font-display text-3xl text-forest">Báo cáo bán hàng</h1>
        <div className="flex flex-wrap items-end gap-4"><label className="text-sm">Từ ngày<input aria-label="Bán hàng từ ngày" type="date" value={dateFrom} onChange={e => setDateFrom(e.target.value)} className="mt-1 block rounded border border-line p-2" /></label><label className="text-sm">Đến ngày<input aria-label="Bán hàng đến ngày" type="date" value={dateTo} onChange={e => setDateTo(e.target.value)} className="mt-1 block rounded border border-line p-2" /></label><button onClick={() => void loadSales()} className="rounded-full border border-forest px-4 py-2 text-sm text-forest">Làm mới số liệu</button></div>
        {salesError && <p role="alert" className="text-danger">{salesError}</p>}
        {sales && <><p className="text-sm text-ink-muted">Theo ngày đặt đơn, từ {sales.date_from} đến {sales.date_to} (giờ Việt Nam). Trạng thái là trạng thái hiện tại của các đơn đặt ngày đó. “Đã xử lý hết” nghĩa là không còn đơn đang xử lý hoặc COD chờ shop nhận tiền; chưa tính các khoản hoàn tiền cần đối soát. Giá trị đơn gồm phí giao hàng; không phải tiền thực nhận sau hoàn. Bấm một chỉ số hoặc dòng để xem các đơn tạo nên số liệu đó.</p><div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">{[["Tổng số đơn", sales.orders, "all"], ["Đơn đã hủy", sales.cancelled_orders, "cancelled"], ["Giá trị đơn không hủy", formatVnd(sales.ordered_value), "ordered"], ["Giá trị đơn đã giao", formatVnd(sales.delivered_value), "delivered"], ["Giá trị đơn đã thanh toán (không hủy)", formatVnd(sales.paid_order_value), "paid"], ["Giảm giá (đơn không hủy)", formatVnd(sales.discount), "discount"]].map(([label,value,metric]) => <Link key={label} href={reportHref(String(metric))} className="rounded-xl border border-line bg-surface p-4 transition hover:border-forest/40 hover:bg-forest/5 focus-visible:outline-2 focus-visible:outline-forest"><span className="text-sm text-ink-muted">{label}</span><strong className="mt-2 block text-xl">{value}</strong></Link>)}</div>
        <DataTable rows={sales.statuses} keyExtractor={r => r.status} onRowClick={r => { window.location.href = reportHref("all", undefined, r.status); }} rowAriaLabel={r => `Xem đơn trạng thái ${r.status}`} empty="Không có đơn hàng trong kỳ." columns={[{key:"status",header:"Trạng thái",cell:r => <StatusBadge status={r.status} />},{key:"orders",header:"Số đơn",cell:r => r.orders},{key:"amount",header:"Giá trị đơn",cell:r => formatVnd(r.amount)}]} />
        <DataTable rows={sales.daily} keyExtractor={r => r.day} onRowClick={r => { window.location.href = reportHref("all", r.day); }} rowAriaLabel={r => `Xem đơn ngày ${r.day}`} empty="Chưa có dữ liệu theo ngày." columns={[
          {key:"day",header:"Ngày đặt",cell:r => r.day},
          {key:"orders",header:"Tổng đơn",cell:r => <strong>{r.orders}</strong>},
          {key:"statuses",header:"Trạng thái các đơn",cell:r => <div className="flex flex-wrap gap-1.5">{r.status_breakdown.map(item => <StatusBadge key={item.status} status={item.status} label={`${item.orders} · ${({pending:"Chờ",confirmed:"Đã xác nhận",packed:"Đã đóng gói",shipped:"Đang giao",delivered:"Đã giao",cancelled:"Đã hủy",returned:"Đã hoàn"} as Record<string,string>)[item.status] ?? item.status}`} />)}{r.cod_pending_orders > 0 && <span className="inline-flex items-center rounded-full border border-danger/20 bg-danger/10 px-2.5 py-0.5 text-xs font-medium text-danger">{r.cod_pending_orders} · COD chờ tiền</span>}</div>},
          {key:"handled",header:"Tình trạng ngày",cell:r => <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${r.handled ? "bg-forest/10 text-forest" : "bg-honey/15 text-ink"}`}>{r.handled ? "Đã xử lý hết" : `Còn ${r.processing_orders + r.cod_pending_orders} đơn`}</span>},
          {key:"amount",header:"Giá trị đã giao",cell:r => formatVnd(r.delivered_value)},
        ]} /></>}
      </section>
      <div>
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h2 className="font-display text-2xl text-forest">Đối chiếu số lượng trong kho</h2>
            <p className="mt-1 text-sm text-ink-muted">
              So sánh số lượng hiện có của từng lô với lịch sử nhập, xuất và điều chỉnh.
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
              onRowClick={setSelectedDrift}
              rowAriaLabel={(l) => `Xem đối chiếu lô ${l.lot_no}`}
              empty="Chưa có lô hàng để đối chiếu."
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
            onRowClick={setSelectedMovement}
            rowAriaLabel={(m) => `Xem bút toán lô ${m.lot_no}`}
            rowClassName={(m, index) => `${movementDayColors.get(movementDay(m)) ? "[&>td:first-child]:border-l-honey" : "[&>td:first-child]:border-l-forest"} [&>td:first-child]:border-l-4 ${index > 0 && movementDay(m) !== movementDay(movements[index - 1]) ? "border-t-2 border-forest/25" : ""}`}
            loading={moveLoading}
            empty="Không có bút toán kho."
          />
        </div>
      </div>
    </div>
  );
}
