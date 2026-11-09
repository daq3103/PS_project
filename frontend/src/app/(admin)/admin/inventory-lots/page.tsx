"use client";
import { DeleteRecordButton } from "@/components/admin/DeleteRecordButton";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  api,
  type InventoryLotOut,
  type ProductDto,
  type StockMovementOut,
} from "@/lib/api-client";
import { DataTable, type Column } from "@/components/admin/DataTable";
import { Drawer } from "@/components/admin/Drawer";
import { FilterBar, FilterField } from "@/components/admin/FilterBar";
import { StatusBadge } from "@/components/admin/StatusBadge";
import { useConfirm } from "@/components/admin/ConfirmDialog";

const REASON_LABELS: Record<string, string> = {
  lot_import: "Nhập lô",
  stocktake_adjust: "Kiểm kê",
  damaged_adjust: "Hư hỏng",
  manual_correct: "Sửa tay",
};

export default function AdminInventoryLotsPage() {
  const [lots, setLots] = useState<InventoryLotOut[]>([]);
  const [products, setProducts] = useState<ProductDto[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [variantFilter, setVariantFilter] = useState("");
  const [stockAlerts, setStockAlerts] = useState<{id:string; product_name:string; title:string; sku:string; quantity:number; threshold:number}[]>([]);
  const [showStockAlerts, setShowStockAlerts] = useState(false);
  const [expiryFilter, setExpiryFilter] = useState<"all" | "expired" | "expiring">("all");
  const [selectedLot, setSelectedLot] = useState<InventoryLotOut | null>(null);
  const [drawerMode, setDrawerMode] = useState<"view" | "adjust">("view");

  const variantMap = useMemo(() => {
    const map = new Map<string, { sku: string; title: string; unit: string }>();
    for (const p of products) {
      for (const v of p.variants) {
        map.set(v.id, { sku: v.sku, title: v.title, unit: v.options?.unit || "cái" });
      }
    }
    return map;
  }, [products]);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const loadProducts = async () => {
        const all: ProductDto[] = [];
        for (let offset = 0; ; offset += 200) {
          const page = await api.adminListProducts(`limit=200&offset=${offset}`);
          all.push(...page);
          if (page.length < 200) return all;
        }
      };
      const [lotsData, prods, alerts] = await Promise.all([
        api.adminListInventoryLots(),
        loadProducts(),
        api.stockAlerts(),
      ]);
      setLots(lotsData);
      setStockAlerts(alerts);
      setProducts(prods);
      setSelectedLot(old => old ? lotsData.find(lot => lot.id === old.id) ?? null : null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Không tải được dữ liệu kho");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    setShowStockAlerts(new URLSearchParams(window.location.search).get("stock") === "low");
    void load();
  }, [load]);

  const filteredLots = useMemo(() => {
    const now = new Date();
    return lots.filter((lot) => {
      const variant = variantMap.get(lot.variant_id);
      const query = variantFilter.trim().toLocaleLowerCase("vi-VN");
      if (query && ![lot.variant_id, lot.lot_no, variant?.sku, variant?.title].some(value => value?.toLocaleLowerCase("vi-VN").includes(query))) return false;
      if (!lot.expiry_date) return expiryFilter === "all";
      if (expiryFilter === "expired") return new Date(lot.expiry_date) <= now;
      if (expiryFilter === "expiring") {
        const d = new Date(lot.expiry_date);
        const days = (d.getTime() - now.getTime()) / (1000 * 60 * 60 * 24);
        return days > 0 && days <= 30;
      }
      return true;
    });
  }, [lots, expiryFilter, variantFilter, variantMap]);

  const columns: Column<InventoryLotOut>[] = [
    { key: "delete", header: "", cell: (l) => <DeleteRecordButton kind="lots" id={l.id} onDeleted={load} /> },
    {
      key: "lot",
      header: "Lô",
      cell: (l) => (
        <div>
          <p className="font-medium">{l.lot_no}</p>
          <p className="font-mono text-xs text-ink-muted">{l.id.slice(0, 8)}…</p>
        </div>
      ),
    },
    {
      key: "variant",
      header: "Biến thể",
      cell: (l) => {
        const v = variantMap.get(l.variant_id);
        return (
          <div>
            <p className="font-medium">{v?.title ?? "—"}</p>
            <p className="text-xs text-ink-muted">{v?.sku ?? l.variant_id.slice(0, 8)}…</p>
          </div>
        );
      },
    },
    { key: "on_hand", header: "Tồn", align: "right", cell: (l) => `${l.qty_on_hand} ${variantMap.get(l.variant_id)?.unit || "cái"}` },
    { key: "reserved", header: "Giữ", align: "right", cell: (l) => `${l.qty_reserved} ${variantMap.get(l.variant_id)?.unit || "cái"}` },
    { key: "available", header: "Khả dụng", align: "right", cell: (l) => `${l.available ?? "—"} ${variantMap.get(l.variant_id)?.unit || "cái"}` },
    {
      key: "expiry",
      header: "HSD",
      cell: (l) => {
        if (!l.expiry_date) return "—";
        const d = new Date(l.expiry_date);
        const days = Math.ceil((d.getTime() - Date.now()) / (1000 * 60 * 60 * 24));
        return (
          <div>
            <p>{d.toLocaleDateString("vi-VN")}</p>
            {days <= 0 && <StatusBadge status="cancelled" label="Hết hạn" />}
            {days > 0 && days <= 30 && <StatusBadge status="pending" label={`${days} ngày`} />}
          </div>
        );
      },
    },
    { key: "status", header: "Trạng thái", cell: (l) => <StatusBadge status={l.status} /> },
    {
      key: "actions",
      header: "",
      cell: (l) => (
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => {
              setSelectedLot(l);
              setDrawerMode("view");
            }}
            className="text-xs text-forest hover:underline"
          >
            Xem sổ
          </button>
          <button
            type="button"
            onClick={() => {
              setSelectedLot(l);
              setDrawerMode("adjust");
            }}
            className="text-xs text-forest hover:underline"
          >
            Điều chỉnh
          </button>
        </div>
      ),
    },
  ];

  return (
    <div>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl text-forest">Lô hàng</h1>
          <p className="mt-1 text-sm text-ink-muted">Nhập lô, ưu tiên hàng gần hết hạn và điều chỉnh số lượng trong kho.</p>
        </div>
      </div>

      {showStockAlerts && <section className="mt-6 rounded-xl border border-honey/30 p-4"><h2 className="font-display text-xl">Mặt hàng hết hoặc sắp hết ({stockAlerts.length})</h2>
        {!stockAlerts.length ? <p className="mt-3">Không có mặt hàng hết hoặc sắp hết.</p> : <ul className="mt-3 divide-y divide-line">{stockAlerts.map(v => <li key={v.id} className="flex flex-wrap justify-between gap-3 py-3"><span>{v.product_name} · {v.title} · {v.sku}</span><strong>Còn {v.quantity} · Ngưỡng {v.threshold}</strong><button className="text-sm text-forest underline" onClick={() => setVariantFilter(v.sku)}>Xem các lô</button></li>)}</ul>}
        <p className="mt-3 text-sm text-ink-muted">Danh sách này gồm cả mẫu chưa có lô nhập. Nhập lô mới để bổ sung tồn kho.</p></section>}
      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <FilterBar>
            <FilterField label="Lọc mẫu hàng">
              <input
                value={variantFilter}
                onChange={(e) => setVariantFilter(e.target.value)}
                placeholder="Mã hàng, tên mẫu hoặc mã lô"
                className="w-48 rounded-sm border border-line bg-paper px-2 py-1.5 font-mono text-xs"
              />
            </FilterField>
            <FilterField label="HSD">
              <select
                value={expiryFilter}
                onChange={(e) => setExpiryFilter(e.target.value as typeof expiryFilter)}
                className="rounded-sm border border-line bg-paper px-2 py-1.5"
              >
                <option value="all">Tất cả</option>
                <option value="expiring">Sắp hết hạn ≤30 ngày</option>
                <option value="expired">Đã hết hạn</option>
              </select>
            </FilterField>
            <button
              type="button"
              onClick={() => void load()}
              className="rounded-full border border-forest px-4 py-1.5 text-sm text-forest hover:bg-forest/8"
            >
              Làm mới
            </button>
          </FilterBar>

          {error && <p className="mt-4 text-sm text-danger">{error}</p>}

          <div className="mt-4">
            <DataTable
              columns={columns}
              rows={filteredLots}
              keyExtractor={(l) => l.id}
              onRowClick={(l) => { setSelectedLot(l); setDrawerMode("view"); }}
              rowAriaLabel={(l) => `Mở sổ lô ${l.lot_no}`}
              loading={loading}
              empty="Không có lô hàng."
            />
          </div>
        </div>

        <div className="space-y-6">
          <CreateLotForm onCreated={load} products={products} />
        </div>
      </div>

      {selectedLot && (
        <LotDrawer
          lot={selectedLot}
          mode={drawerMode}
          onClose={() => setSelectedLot(null)}
          onMutated={load}
        />
      )}
    </div>
  );
}

function CreateLotForm({
  onCreated,
  products,
}: {
  onCreated: () => void;
  products: ProductDto[];
}) {
  const [productId, setProductId] = useState("");
  const [variantId, setVariantId] = useState("");
  const [lotNo, setLotNo] = useState("");
  const [qty, setQty] = useState("10");
  const [unitCost, setUnitCost] = useState("10000");
  const [expiry, setExpiry] = useState("");
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const selectedProduct = useMemo(
    () => products.find((p) => p.id === productId),
    [products, productId],
  );
  const selectedUnit = selectedProduct?.variants.find(v => v.id === variantId)?.options?.unit || "cái";

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError("");
    try {
      await api.adminCreateInventoryLot({
        variant_id: variantId.trim(),
        lot_no: lotNo.trim(),
        qty: Number(qty) || 0,
        unit_cost: Number(unitCost) || 0,
        expiry_date: expiry || null,
        note: note.trim() || undefined,
      });
      setLotNo("");
      setQty("10");
      setExpiry("");
      setNote("");
      onCreated();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Tạo lô thất bại");
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={submit} className="rounded-sm border border-line bg-surface p-4">
      <h2 className="font-display text-xl text-forest">Nhập lô mới</h2>
      <div className="mt-4 grid gap-3">
        <label className="text-sm">
          <span className="text-ink-muted">Sản phẩm</span>
          <select
            value={productId}
            onChange={(e) => {
              setProductId(e.target.value);
              setVariantId("");
            }}
            className="mt-1 block w-full rounded-sm border border-line bg-paper px-2 py-1.5"
          >
            <option value="">Chọn sản phẩm</option>
            {products.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </label>
        <label className="text-sm">
          <span className="text-ink-muted">Biến thể</span>
          <select
            value={variantId}
            onChange={(e) => setVariantId(e.target.value)}
            required
            disabled={!selectedProduct}
            className="mt-1 block w-full rounded-sm border border-line bg-paper px-2 py-1.5 disabled:opacity-50"
          >
            <option value="">Chọn biến thể</option>
            {selectedProduct?.variants.map((v) => (
              <option key={v.id} value={v.id}>
                {v.title} ({v.sku}) · {v.options?.unit || "cái"}
              </option>
            ))}
          </select>
        </label>
        <Field label="Mã lô" value={lotNo} onChange={setLotNo} required />
        <Field label={`Số lượng nhập (${selectedUnit})`} value={qty} onChange={setQty} type="number" required />
        <p className="text-xs text-ink-muted">Mỗi 1 đơn vị là 1 biến thể đã chọn. Ví dụ: 10 túi hoặc 2 tải.</p>
        <Field label="Giá vốn (đ)" value={unitCost} onChange={setUnitCost} type="number" required />
        <Field label="Hạn dùng" value={expiry} onChange={setExpiry} type="date" />
        <Field label="Ghi chú" value={note} onChange={setNote} />
      </div>
      {error && <p className="mt-3 text-sm text-danger">{error}</p>}
      <button
        type="submit"
        disabled={saving}
        className="mt-4 w-full rounded-full bg-forest px-4 py-2 text-sm font-medium text-white hover:bg-forest-deep disabled:opacity-50"
      >
        {saving ? "Đang lưu…" : "Tạo lô"}
      </button>
    </form>
  );
}

function LotDrawer({
  lot,
  mode,
  onClose,
  onMutated,
}: {
  lot: InventoryLotOut;
  mode: "view" | "adjust";
  onClose: () => void;
  onMutated: () => void | Promise<void>;
}) {
  const [movements, setMovements] = useState<StockMovementOut[]>([]);
  const [loadingMovements, setLoadingMovements] = useState(false);
  const [delta, setDelta] = useState("");
  const [reason, setReason] = useState<"stocktake_adjust" | "damaged_adjust" | "manual_correct">(
    "stocktake_adjust",
  );
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const { confirm, dialog } = useConfirm();

  const loadMovements = useCallback(async () => {
    setLoadingMovements(true);
    try {
      const data = await api.adminListStockMovements({
        lot_id: lot.id,
        limit: 50,
      });
      setMovements(data);
    } finally {
      setLoadingMovements(false);
    }
  }, [lot.id]);

  useEffect(() => {
    void loadMovements();
  }, [loadMovements]);

  async function adjust(e: React.FormEvent) {
    e.preventDefault();
    const ok = await confirm({
      title: "Xác nhận điều chỉnh",
      message: `Ghi điều chỉnh ${delta} vào lô ${lot.lot_no}?`,
      confirmText: "Ghi",
    });
    if (!ok) return;
    setSaving(true);
    setError("");
    try {
      await api.adminAdjustStock({
        lot_id: lot.id,
        qty_delta: Number(delta) || 0,
        reason,
        note: note.trim() || undefined,
      });
      setDelta("");
      setNote("");
      await onMutated();
      await loadMovements();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Điều chỉnh thất bại");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Drawer
      open
      onClose={onClose}
      title={mode === "adjust" ? `Điều chỉnh lô ${lot.lot_no}` : `Lô ${lot.lot_no}`}
    >
      {dialog}
      <div className="space-y-6">
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <p className="text-ink-muted">Tồn</p>
            <p className="font-display text-xl">{lot.qty_on_hand}</p>
          </div>
          <div>
            <p className="text-ink-muted">Khả dụng</p>
            <p className="font-display text-xl">{lot.available ?? "—"}</p>
          </div>
        </div>

        {mode === "adjust" && (
          <form onSubmit={adjust} className="rounded-sm border border-line bg-surface p-4">
            <h3 className="font-medium">Ghi điều chỉnh</h3>
            <div className="mt-3 grid gap-3">
              <Field label="Delta (+/−)" value={delta} onChange={setDelta} type="number" required />
              <label className="text-sm">
                <span className="text-ink-muted">Lý do</span>
                <select
                  value={reason}
                  onChange={(e) => setReason(e.target.value as typeof reason)}
                  className="mt-1 block w-full rounded-sm border border-line bg-paper px-2 py-1.5"
                >
                  <option value="stocktake_adjust">Kiểm kê</option>
                  <option value="damaged_adjust">Hư hỏng</option>
                  <option value="manual_correct">Sửa tay</option>
                </select>
              </label>
              <Field label="Ghi chú" value={note} onChange={setNote} />
            </div>
            {error && <p className="mt-3 text-sm text-danger">{error}</p>}
            <button
              type="submit"
              disabled={saving}
              className="mt-4 rounded-full bg-forest px-4 py-2 text-sm font-medium text-white hover:bg-forest-deep disabled:opacity-50"
            >
              {saving ? "Đang lưu…" : "Ghi điều chỉnh"}
            </button>
          </form>
        )}

        <div>
          <h3 className="font-medium">Sổ kho gần đây</h3>
          <div className="mt-2 overflow-hidden rounded-sm border border-line bg-surface">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-line bg-forest/5">
                <tr>
                  <th className="px-3 py-2 text-ink-muted">Thời gian</th>
                  <th className="px-3 py-2 text-ink-muted">SL</th>
                  <th className="px-3 py-2 text-ink-muted">Lý do</th>
                  <th className="px-3 py-2 text-ink-muted">Ghi chú</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {loadingMovements ? (
                  <tr>
                    <td colSpan={4} className="px-3 py-4 text-center text-ink-muted">
                      Đang tải…
                    </td>
                  </tr>
                ) : movements.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="px-3 py-4 text-center text-ink-muted">
                      Chưa có dữ liệu.
                    </td>
                  </tr>
                ) : (
                  movements.map((m) => (
                    <tr key={m.id}>
                      <td className="px-3 py-2">
                        {new Date(m.created_at).toLocaleString("vi-VN")}
                      </td>
                      <td
                        className={`px-3 py-2 font-mono ${
                          m.qty_delta > 0 ? "text-forest" : "text-danger"
                        }`}
                      >
                        {m.qty_delta > 0 ? `+${m.qty_delta}` : m.qty_delta}
                      </td>
                      <td className="px-3 py-2">
                        {REASON_LABELS[m.reason] ?? m.reason}
                      </td>
                      <td className="px-3 py-2 text-ink-muted">{m.note ?? "—"}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </Drawer>
  );
}

function Field({
  label,
  value,
  onChange,
  type = "text",
  required,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  type?: string;
  required?: boolean;
}) {
  return (
    <label className="block text-sm">
      <span className="text-ink-muted">{label}</span>
      <input
        type={type}
        value={value}
        required={required}
        onChange={(e) => onChange(e.target.value)}
        className="mt-1 block w-full rounded-sm border border-line bg-paper px-2 py-1.5 outline-none focus:border-moss"
      />
    </label>
  );
}
