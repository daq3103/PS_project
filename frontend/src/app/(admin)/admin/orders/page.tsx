"use client";
import { DeleteRecordButton } from "@/components/admin/DeleteRecordButton";

import { useCallback, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  api,
  type OrderDetailOut,
  type OrderOut,
} from "@/lib/api-client";
import { formatVnd } from "@/lib/format";
import { DataTable, type Column } from "@/components/admin/DataTable";
import { Drawer } from "@/components/admin/Drawer";
import { StatusBadge } from "@/components/admin/StatusBadge";
import { FilterBar, FilterField } from "@/components/admin/FilterBar";
import { useConfirm } from "@/components/admin/ConfirmDialog";

const STATUS_LABELS: Record<string, string> = {
  pending: "Chờ",
  confirmed: "Xác nhận",
  packed: "Đóng gói",
  shipped: "Đang giao",
  delivered: "Đã giao",
  cancelled: "Huỷ",
};

function ShipmentForm({
  order,
  onCreated,
  disabled,
}: {
  order: OrderOut;
  onCreated: () => void;
  disabled?: boolean;
}) {
  const [packageCount, setPackageCount] = useState("1");
  const [weightGrams, setWeightGrams] = useState("");
  const [carrier, setCarrier] = useState("ghn");
  const [tracking, setTracking] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit() {
    setBusy(true);
    setError("");
    try {
      const weight = Number(weightGrams);
      await api.manualShipment(order.id, {
        carrier_code: carrier,
        tracking_code: tracking.trim(),
        package_count: Number(packageCount) || 1,
        total_weight_grams: weight,
      });
      onCreated();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Tạo vận đơn thất bại");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rounded-sm border border-line bg-surface p-4">
      <h4 className="font-medium">Ghi nhận vận đơn</h4>
      <p className="mt-1 text-xs text-ink-muted">Tạo đơn giao hàng với hãng vận chuyển rồi nhập mã tại đây.</p>
      <label className="mt-3 block text-sm">Hãng vận chuyển<select value={carrier} onChange={e => setCarrier(e.target.value)} className="mt-1 block w-full rounded-lg border border-line bg-paper p-2"><option value="ghn">Giao Hàng Nhanh</option><option value="ghtk">Giao Hàng Tiết Kiệm</option><option value="viettel_post">Viettel Post</option><option value="other">Đơn vị khác</option></select></label>
      <label className="mt-3 block text-sm">Mã vận đơn<input value={tracking} maxLength={100} onChange={e => setTracking(e.target.value)} className="mt-1 block w-full rounded-lg border border-line bg-paper p-2" /></label>
      <div className="mt-3 grid grid-cols-2 gap-3">
        <label className="text-sm">
          <span className="text-ink-muted">Số kiện</span>
          <input
            type="number"
            min={1}
            max={10}
            value={packageCount}
            onChange={(e) => setPackageCount(e.target.value)}
            className="mt-1 block w-full rounded-sm border border-line bg-paper px-2 py-1.5"
          />
        </label>
        <label className="text-sm">
          <span className="text-ink-muted">Cân nặng (g)</span>
          <input
            type="number"
            min={1}
            value={weightGrams}
            onChange={(e) => setWeightGrams(e.target.value)}
            placeholder="Cả hàng và bao bì"
            className="mt-1 block w-full rounded-sm border border-line bg-paper px-2 py-1.5"
          />
        </label>
      </div>
      {error && <p className="mt-2 text-xs text-danger">{error}</p>}
      <button
        type="button"
        disabled={busy || disabled || !tracking.trim() || Number(weightGrams) <= 0}
        onClick={() => void submit()}
        className="mt-3 rounded-full bg-forest px-4 py-1.5 text-sm font-medium text-white hover:bg-forest-deep disabled:opacity-50"
      >
        {busy ? "Đang lưu…" : "Lưu vận đơn"}
      </button>
    </div>
  );
}

function OrderDetailDrawer({
  orderId,
  open,
  onClose,
  onMutated,
}: {
  orderId: string | null;
  open: boolean;
  onClose: () => void;
  onMutated: () => void;
}) {
  const [order, setOrder] = useState<OrderDetailOut | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const { confirm, dialog } = useConfirm();
  const [deliveryNote, setDeliveryNote] = useState("");
  const [codReceived, setCodReceived] = useState(false);
  const [codNote, setCodNote] = useState("");

  useEffect(() => {
    setDeliveryNote("");
    setCodReceived(false);
    setCodNote("");
  }, [orderId]);

  const load = useCallback(async () => {
    if (!orderId) return;
    setLoading(true);
    setError("");
    try {
      setOrder(await api.adminGetOrderDetail(orderId));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Không tải được đơn");
    } finally {
      setLoading(false);
    }
  }, [orderId]);

  useEffect(() => {
    if (open) void load();
  }, [open, load]);

  async function act(label: string, fn: () => Promise<unknown>, needsReason = false) {
    let reason: string | undefined;
    if (needsReason) {
      const ok = await confirm({
        title: label === "Xác nhận" ? "Xác nhận đơn hàng" : label,
        message: `Bạn có chắc muốn ${label.toLowerCase().replace(/ đơn$/, "")} đơn hàng này?`,
        variant: "danger",
        confirmText: label,
      });
      if (!ok) return;
      reason = window.prompt("Lý do (tuỳ chọn):") ?? undefined;
    } else {
      const ok = await confirm({
        title: label === "Xác nhận" ? "Xác nhận đơn hàng" : label,
        message: `Thực hiện ${label.toLowerCase()} cho đơn ${order?.order_code ?? ""}?`,
        confirmText: label,
      });
      if (!ok) return;
    }
    try {
      await fn();
      await load();
      onMutated();
    } catch (e) {
      setError(e instanceof Error ? e.message : `${label} thất bại`);
    }
  }

  return (
    <Drawer open={open} onClose={onClose} title={`Đơn ${order?.order_code ?? orderId ?? ""}`}>
      {dialog}
      {loading && <p className="text-ink-muted">Đang tải…</p>}
      {error && <p className="text-sm text-danger">{error}</p>}
      {order && !loading && (
        <div className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <p className="text-xs text-ink-muted">Khách hàng</p>
              <p className="font-medium">{order.customer_name}</p>
              <p className="text-sm text-ink-muted">{order.customer_phone}</p>
              {order.customer_email && (
                <p className="text-sm text-ink-muted">{order.customer_email}</p>
              )}
            </div>
            <div>
              <p className="text-xs text-ink-muted">Địa chỉ giao</p>
              <p className="text-sm">
                {order.shipping_address
                  ? order.shipping_address.full_address ?? `${order.shipping_address.street_address ?? order.shipping_address.street ?? ""}, ${order.shipping_address.ward_name ?? order.shipping_address.ward ?? ""}, ${order.shipping_address.district_name ?? order.shipping_address.district ?? ""}, ${order.shipping_address.province_name ?? order.shipping_address.province ?? ""}`
                  : "—"}
              </p>
            </div>
            <div>
              <p className="text-xs text-ink-muted">Trạng thái</p>
              <StatusBadge status={order.status} />
            </div>
            <div>
              <p className="text-xs text-ink-muted">Thanh toán</p>
              <StatusBadge status={order.payment_status} />
              <span className="ml-2 text-sm text-ink-muted">{order.payment_method}</span>
            </div>
            <div>
              <p className="text-xs text-ink-muted">Tổng đơn</p>
              <p className="font-display text-xl">{formatVnd(order.total_amount)}</p>
              {order.subtotal_amount != null && (
                <p className="text-xs text-ink-muted">
                  Tạm tính {formatVnd(order.subtotal_amount)}
                  {order.discount_amount ? ` · Giảm ${formatVnd(order.discount_amount)}` : ""}
                  {order.shipping_fee != null ? ` · Ship ${formatVnd(order.shipping_fee)}` : ""}
                </p>
              )}
            </div>
            <div>
              <p className="text-xs text-ink-muted">Đặt lúc</p>
              <p className="text-sm">{new Date(order.created_at).toLocaleString("vi-VN")}</p>
            </div>
          </div>

          {order.fulfillment && (
            <div className="rounded-sm border border-line bg-surface p-4">
              <h4 className="font-medium">Vận chuyển</h4>
              <div className="mt-2 space-y-1 text-sm">
                <p>
                  <span className="text-ink-muted">Mã vận đơn:</span>{" "}
                  <span className="font-mono">{order.fulfillment.tracking_code ?? "—"}</span>
                </p>
                <p>
                  <span className="text-ink-muted">Đơn vị:</span> {order.fulfillment.carrier_code}
                </p>
                <p>
                  <span className="text-ink-muted">Kiện / trọng lượng:</span>{" "}
                  {order.fulfillment.package_count} kiện · {order.fulfillment.total_weight_grams}g
                </p>
                {order.fulfillment.label_print_url && (
                  <p>
                    <a
                      href={order.fulfillment.label_print_url}
                      target="_blank"
                      rel="noreferrer"
                      className="font-medium text-forest hover:underline"
                    >
                      In phiếu giao
                    </a>
                  </p>
                )}
              </div>
            </div>
          )}

          <div>
            <h4 className="font-medium">Sản phẩm</h4>
            <ul className="mt-2 divide-y divide-line rounded-sm border border-line bg-surface text-sm">
              {order.items.map((item) => (
                <li key={item.id} className="flex items-start justify-between px-4 py-3">
                  <div>
                    <p className="font-medium">{item.product_name_snapshot}</p>
                    <p className="text-xs text-ink-muted">
                      {item.variant_title_snapshot} · {item.sku_snapshot} · SL {item.qty}
                    </p>
                  </div>
                  <p className="font-mono">{formatVnd(item.line_total)}</p>
                </li>
              ))}
            </ul>
          </div>

          <div>
            <h4 className="font-medium">Lịch sử trạng thái</h4>
            <ul className="mt-2 space-y-2">
              {order.status_history.map((h) => (
                <li key={h.id} className="flex gap-3 text-sm">
                  <span className="text-ink-muted">
                    {new Date(h.created_at).toLocaleString("vi-VN")}
                  </span>
                  <span>
                    {h.from_status ? `${STATUS_LABELS[h.from_status] ?? h.from_status} → ` : ""}
                    <span className="font-medium">{STATUS_LABELS[h.to_status] ?? h.to_status}</span>
                  </span>
                  <span className="text-ink-muted">({h.actor_type})</span>
                  {h.note && <span className="text-ink-muted">{h.note}</span>}
                </li>
              ))}
            </ul>
          </div>

          <div className="flex flex-wrap gap-2 border-t border-line pt-4">
            {order.status === "pending" && (
              <ActionBtn
                label="Xác nhận"
                onClick={() => void act("Xác nhận", () => api.adminConfirmOrder(order.id))}
              />
            )}
            {order.status === "confirmed" && (
              <ActionBtn
                label="Đóng gói"
                onClick={() => void act("Đóng gói", () => api.adminPackOrder(order.id))}
              />
            )}
            {(order.status === "confirmed" || order.status === "packed") && !order.tracking_code && (
              <ShipmentForm order={order} onCreated={() => void act("Tải lại", async () => {})} />
            )}
            {order.status === "packed" && (
              <ActionBtn
                label="Giao hàng"
                onClick={() => void act("Giao hàng", () => api.adminShipOrder(order.id))}
              />
            )}
            {order.status === "shipped" && <div className="w-full rounded-lg border border-line bg-surface p-3"><p className="text-sm font-medium">Xác nhận giao thành công</p><p className="mt-1 text-xs text-ink-muted">Chỉ dùng sau khi kiểm tra trạng thái với hãng vận chuyển hoặc người giao.</p><label className="mt-2 block text-sm">Căn cứ xác nhận giao<input value={deliveryNote} onChange={e => setDeliveryNote(e.target.value)} placeholder="Ví dụ: người giao báo đã giao, mã vận đơn…" minLength={10} maxLength={500} className="mt-1 block w-full rounded border border-line p-2" /></label>{order.payment_method === "cod" && <><label className="mt-3 flex items-center gap-2 text-sm"><input type="checkbox" checked={codReceived} onChange={e => setCodReceived(e.target.checked)} />Shop đã thực nhận đủ {formatVnd(order.total_amount)} tiền COD</label>{codReceived && <label className="mt-2 block text-sm">Căn cứ shop nhận tiền<input value={codNote} onChange={e => setCodNote(e.target.value)} placeholder="Ví dụ: nhân viên giao nộp tiền mặt, mã chuyển khoản…" maxLength={500} className="mt-1 block w-full rounded border border-line p-2" /></label>}<p className="mt-1 text-xs text-ink-muted">Nếu tiền còn ở người giao hoặc hãng vận chuyển, để trống ô này. Có thể đối soát sau.</p></>}<button type="button" disabled={deliveryNote.trim().length < 10 || (codReceived && codNote.trim().length < 10)} onClick={() => void act("Đã giao", () => api.confirmManualDelivery(order.id, deliveryNote.trim(), codReceived, codNote.trim()))} className="mt-3 rounded-full bg-forest px-4 py-2 text-sm text-white disabled:opacity-50">{codReceived ? "Đã giao và đã nhận COD" : "Đánh dấu đã giao"}</button></div>}
            {order.status === "delivered" && order.payment_method === "cod" && order.payment_status === "unpaid" && <div className="w-full rounded-lg border border-honey/40 bg-honey/5 p-3"><p className="text-sm font-medium">COD chờ shop nhận tiền</p><p className="mt-1 text-xs text-ink-muted">Chỉ xác nhận khi tiền đã thực về shop. Đơn sẽ chuyển sang mục Đã hoàn tất.</p><label className="mt-2 block text-sm">Căn cứ shop nhận tiền<input value={codNote} onChange={e => setCodNote(e.target.value)} placeholder="Người giao nộp tiền, mã chuyển khoản hoặc biên bản đối soát…" maxLength={500} className="mt-1 block w-full rounded border border-line p-2" /></label><button type="button" disabled={codNote.trim().length < 10} onClick={() => void act("Đã nhận COD", () => api.recordCodReceipt(order.id, codNote.trim()))} className="mt-3 rounded-full bg-forest px-4 py-2 text-sm text-white disabled:opacity-50">Xác nhận đã nhận COD</button></div>}
            {order.status !== "shipped" && order.status !== "delivered" && order.status !== "cancelled" && (
              <ActionBtn
                label="Huỷ đơn"
                danger
                onClick={() =>
                  void act("Huỷ đơn", () => api.cancelOrder(order.id, undefined), true)
                }
              />
            )}
          </div>
        </div>
      )}
    </Drawer>
  );
}

function ActionBtn({
  label,
  onClick,
  danger,
}: {
  label: string;
  onClick: () => void;
  danger?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-full px-4 py-1.5 text-sm font-medium ${
        danger
          ? "border border-danger text-danger hover:bg-danger/5"
          : "bg-forest text-white hover:bg-forest-deep"
      }`}
    >
      {label}
    </button>
  );
}

export default function AdminOrdersPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [orders, setOrders] = useState<OrderOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [status, setStatus] = useState(searchParams.get("status") ?? "");
  const [payment, setPayment] = useState(searchParams.get("payment_method") ?? "");
  const [q, setQ] = useState(searchParams.get("q") ?? "");
  const [dateFrom, setDateFrom] = useState(searchParams.get("date_from") ?? "");
  const [dateTo, setDateTo] = useState(searchParams.get("date_to") ?? "");
  const [reportMetric, setReportMetric] = useState(searchParams.get("report_metric") ?? "");
  const [view, setView] = useState<"active" | "closed" | "all">(() => {
    const requested = searchParams.get("view");
    if (requested === "active" || requested === "closed" || requested === "all") return requested;
    return searchParams.get("report_metric") || searchParams.get("status") ? "all" : "active";
  });
  const [offset, setOffset] = useState(0);
  const [openOrderId, setOpenOrderId] = useState<string | null>(searchParams.get("open"));

  const { confirm, dialog } = useConfirm();

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await api.adminListOrders({
        view,
        status: status || undefined,
        payment_method: payment || undefined,
        q: q || undefined,
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
        report_metric: reportMetric || undefined,
        limit: 50,
        offset,
      });
      setOrders(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Không tải được danh sách đơn");
    } finally {
      setLoading(false);
    }
  }, [view, status, payment, q, dateFrom, dateTo, reportMetric, offset]);

  useEffect(() => {
    void load();
  }, [load]);

  function updateSearch(params: Record<string, string>) {
    const sp = new URLSearchParams(searchParams.toString());
    Object.entries(params).forEach(([k, v]) => {
      if (v) sp.set(k, v);
      else sp.delete(k);
    });
    router.replace(`/admin/orders?${sp.toString()}`, { scroll: false });
  }

  async function rowAction(label: string, id: string, fn: () => Promise<unknown>) {
    const ok = await confirm({
      title: label === "Xác nhận" ? "Xác nhận đơn hàng" : label,
      message: `Thực hiện ${label.toLowerCase()} cho đơn đã chọn?`,
      confirmText: label,
    });
    if (!ok) return;
    try {
      await fn();
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : `${label} thất bại`);
    }
  }

  const columns: Column<OrderOut>[] = [
    { key: "delete", header: "", cell: (o) => <DeleteRecordButton kind="orders" id={o.id} onDeleted={load} /> },
    {
      key: "code",
      header: "Mã đơn",
      cell: (o) => (
        <button
          type="button"
          onClick={() => {
            setOpenOrderId(o.id);
            updateSearch({ open: o.id });
          }}
          className="font-mono text-forest hover:underline"
        >
          {o.order_code}
        </button>
      ),
    },
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
    {
      key: "total",
      header: "Tổng",
      align: "right",
      width: "w-28",
      cell: (o) => formatVnd(o.total_amount),
    },
    {
      key: "status",
      header: "Trạng thái",
      width: "w-32",
      cell: (o) => <StatusBadge status={o.status} />,
    },
    {
      key: "payment",
      header: "Thanh toán",
      width: "w-36",
      cell: (o) => (
        <div className="space-y-1">
          <StatusBadge status={o.payment_status} />
          <p className="text-xs text-ink-muted">{o.payment_method}</p>
        </div>
      ),
    },
    {
      key: "created",
      header: "Thời gian",
      width: "w-40",
      cell: (o) => new Date(o.created_at).toLocaleString("vi-VN"),
    },
    {
      key: "actions",
      header: "",
      width: "w-48",
      cell: (o) => (
        <div className="flex flex-wrap gap-1">
          {o.status === "pending" && (
            <MiniBtn
              label="Xác nhận"
              onClick={() => void rowAction("xác nhận", o.id, () => api.adminConfirmOrder(o.id))}
            />
          )}
          {o.status === "confirmed" && (
            <MiniBtn
              label="Đóng gói"
              onClick={() => void rowAction("đóng gói", o.id, () => api.adminPackOrder(o.id))}
            />
          )}
          {o.status === "packed" && (
            <MiniBtn
              label="Giao"
              onClick={() => void rowAction("giao hàng", o.id, () => api.adminShipOrder(o.id))}
            />
          )}
          {(o.status === "confirmed" || o.status === "packed") && !o.tracking_code && (
            <MiniBtn
              label="Vận đơn"
              onClick={() => {
                setOpenOrderId(o.id);
                updateSearch({ open: o.id });
              }}
            />
          )}
        </div>
      ),
    },
  ];

  return (
    <div>
      {dialog}
      <OrderDetailDrawer
        orderId={openOrderId}
        open={!!openOrderId}
        onClose={() => {
          setOpenOrderId(null);
          updateSearch({ open: "" });
        }}
        onMutated={load}
      />

      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl text-forest">Đơn hàng</h1>
          <p className="mt-1 text-sm text-ink-muted">Đơn đang xử lý và COD chưa nhận tiền ở mục Cần xử lý. Đơn hoàn tất vẫn tra cứu được.</p>
        </div>
        <button
          type="button"
          onClick={() => { setStatus(""); setPayment(""); setQ(""); setDateFrom(""); setDateTo(""); setReportMetric(""); setView("active"); setOffset(0); router.replace("/admin/orders", {scroll:false}); }}
          className="rounded-full border border-line px-4 py-1.5 text-sm text-ink-muted hover:border-forest hover:text-forest"
        >
          Xoá bộ lọc
        </button>
      </div>

      <div className="mt-5 flex flex-wrap gap-2" role="group" aria-label="Nhóm đơn hàng">{([['active','Cần xử lý'],['closed','Đã hoàn tất'],['all','Tất cả']] as const).map(([value,label]) => <button key={value} type="button" aria-pressed={view === value} onClick={() => { setView(value); setOffset(0); updateSearch({view:value}); }} className={`rounded-full border px-4 py-2 text-sm ${view === value ? "border-forest bg-forest text-white" : "border-line text-ink hover:border-forest/40 hover:bg-forest/5"}`}>{label}</button>)}</div>
      <FilterBar>
        <FilterField label="Trạng thái">
          <select
            value={status}
            onChange={(e) => {
              setStatus(e.target.value);
              setView("all");
              setOffset(0);
              updateSearch({ status: e.target.value, view: "all" });
            }}
            className="rounded-sm border border-line bg-paper px-2 py-1.5"
          >
            <option value="">Tất cả</option>
            {Object.entries(STATUS_LABELS).map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </select>
        </FilterField>
        <FilterField label="Thanh toán">
          <select
            value={payment}
            onChange={(e) => {
              setPayment(e.target.value);
              updateSearch({ payment_method: e.target.value });
            }}
            className="rounded-sm border border-line bg-paper px-2 py-1.5"
          >
            <option value="">Tất cả</option>
            <option value="cod">COD</option>
            <option value="vietqr">VietQR</option>
          </select>
        </FilterField>
        <FilterField label="Tìm kiếm">
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onBlur={() => updateSearch({ q })}
            onKeyDown={(e) => e.key === "Enter" && updateSearch({ q })}
            placeholder="Mã đơn / SĐT / Tên"
            className="w-48 rounded-sm border border-line bg-paper px-2 py-1.5"
          />
        </FilterField>
        <FilterField label="Từ ngày">
          <input
            type="date"
            value={dateFrom}
            onChange={(e) => {
              setDateFrom(e.target.value);
              updateSearch({ date_from: e.target.value });
            }}
            className="rounded-sm border border-line bg-paper px-2 py-1.5"
          />
        </FilterField>
        <FilterField label="Đến ngày">
          <input
            type="date"
            value={dateTo}
            onChange={(e) => {
              setDateTo(e.target.value);
              updateSearch({ date_to: e.target.value });
            }}
            className="rounded-sm border border-line bg-paper px-2 py-1.5"
          />
        </FilterField>
      </FilterBar>

      {error && <p className="mt-4 text-sm text-danger">{error}</p>}

      <div className="mt-4">
        {reportMetric && <p className="mb-3 text-sm text-forest">Chi tiết từ báo cáo bán hàng: {({all:"Tổng số đơn",cancelled:"Đơn đã hủy",ordered:"Đơn không hủy",delivered:"Đơn đã giao",paid:"Đơn đã thanh toán",discount:"Đơn có giảm giá"} as Record<string,string>)[reportMetric] ?? reportMetric}</p>}
        <DataTable
          columns={columns}
          rows={orders}
          keyExtractor={(o) => o.id}
          onRowClick={(o) => { setOpenOrderId(o.id); updateSearch({ open: o.id }); }}
          rowAriaLabel={(o) => `Mở chi tiết đơn ${o.order_code}`}
          loading={loading}
          empty="Không có đơn hàng phù hợp."
        />
        <div className="mt-4 flex items-center gap-3 text-sm"><button type="button" disabled={offset === 0 || loading} onClick={() => setOffset(value => Math.max(0, value - 50))} className="rounded-full border border-line px-4 py-2 disabled:opacity-40">Trang trước</button><span>Trang {Math.floor(offset / 50) + 1}</span><button type="button" disabled={orders.length < 50 || loading} onClick={() => setOffset(value => value + 50)} className="rounded-full border border-line px-4 py-2 disabled:opacity-40">Trang sau</button></div>
      </div>
    </div>
  );
}

function MiniBtn({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="rounded-full border border-forest px-2 py-0.5 text-xs text-forest hover:bg-forest/8"
    >
      {label}
    </button>
  );
}
